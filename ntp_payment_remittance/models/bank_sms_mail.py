import json
import re
import logging
from datetime import datetime
from odoo import api, models, fields, tools
from textfsm import TextFSM
from io import StringIO
import pytz

_logger = logging.getLogger(__name__)

MAX_PARSE_RUN = 5


POSSIBLE_DATETIME_FORMAT = [
    "%B %d, %Y at %H:%M%p",  # bank noti
    "%d-%m-%Y/%H:%M", # credit noti
    "%m/%d/%y %I:%M %p",  # 7/27/22 3:29 PM or 7/11/22 1:09 PM
]


class BankSmsMail(models.Model):
    _name = "bank.sms.mail"
    _description = "Bank Sms Mail"
    _order = "received_date desc"

    bank_sms_id = fields.Many2one("bank.sms", "Bank Sms")
    bank_sms_transaction_ids = fields.One2many(
        "bank.sms.transaction", "bank_sms_mail_id"
    )
    bank_sms_transaction_count = fields.Integer(
        "# Transactions", compute="_compute_bank_sms_transaction_count"
    )

    state = fields.Selection(
        [
            ("draft", "draft"),  # default
            (
                "processing",
                "Processing",
            ),  # processing mean, run once or more but cannot parse
            ("done", "Done"),  # can parse and save data
            (
                "ignore",
                "Ignore",
            ),  # exceed number of processing time, ignore will note this mail is skipped for next turn processing
        ],
        "State",
        default="draft",
    )

    message_id = fields.Char("Message Id", readonly=True, required=True)
    received_date = fields.Datetime("Received Date")
    from_address = fields.Char("From", readonly=True, required=True)
    subject = fields.Char("Subject", readonly=True, required=True)
    html_body = fields.Text("Body")
    text_body = fields.Text("Text Only Body")
    cleaned_text_body = fields.Text("Cleaned Text Only Body")
    message_dict = fields.Text("Message Dict")

    parsed_count = fields.Integer("#. Parse Run", default=0)

    def name_get(self):
        result = []
        for record in self:
            rec_name = "MAIL/{}/{}".format(
                record.id, record.received_date.strftime("%y-%b-%d").upper()
            )
            result.append((record.id, rec_name))
        return result

    def _compute_bank_sms_transaction_count(self):
        for rec in self:
            rec.bank_sms_transaction_count = len(rec.bank_sms_transaction_ids)

    def _parse(self):
        self.ensure_one()
        created_transactions = []
        try:
            for tmpl in self.bank_sms_id.bank_sms_transaction_parser_ids:
                parser = TextFSM(StringIO(tmpl.text_fsm.strip()))
                parsed = parser.ParseText(self.cleaned_text_body)
                for line in parsed:
                    if line:
                        # fmt: off
                        account_alias, sign, amount, amount_currency, balance, balance_currency, message, date = line
                        alias_names = [x.name for x in self.bank_sms_id.bank_sms_aliases]
                        journal_id = self.bank_sms_id._find_journal_from_mail(json.loads(self.message_dict))
                        # this is prevent case, to make sure tranaction match alias name
                        if journal_id and (account_alias in alias_names):
                            alias_id = [x for x in self.bank_sms_id.bank_sms_aliases if x.name == account_alias][0]
                            try:
                                currency_id = self.env['res.currency'].search([('name', '=', amount_currency)])[0].id
                            except:
                                currency_id = alias_id.default_currency_id.id
                            if sign in ['-', '+', 'debit', 'credit']:
                                payment_type = "outbound" if sign in ['-', 'debit'] else 'inbound'
                            elif alias_id.bank_account_type in ['credit_card', 'debit_card']:
                                payment_type = "outbound"
                            else:
                                continue

                            received_date = None
                            # date may be different since we need approval so message noti can be lagged behind actual transaction date
                            for date_fmt in POSSIBLE_DATETIME_FORMAT:
                                try:
                                    received_date = datetime.strptime(date, date_fmt)
                                    # ! convert time to utc time
                                    # FIXME: we hard code it here
                                    timezone = 'Asia/Saigon'
                                    local_time = pytz.timezone(timezone)
                                    local_datetime = local_time.localize(received_date)
                                    received_date = local_datetime.astimezone(pytz.utc).replace(tzinfo=None)
                                    break
                                except ValueError:
                                    continue
                            if not received_date:
                                received_date = self.received_date
                            vals_2_create = {
                                "bank_sms_mail_id": self.id,
                                # "received_date": False,
                                # January 28, 2022 at 09:35AM -> parse it
                                "received_date": received_date,
                                "payment_type": payment_type,
                                # will be problem if currency like $, charging $ 0.14 for example
                                "amount": float(re.sub("[^\d]", "", amount)),
                                "balance": float(re.sub("[^\d]", "", balance)),
                                "message": message,
                                "currency_id": currency_id,
                                "transaction_id": self.message_id,
                                "journal_id": journal_id.id
                            }
                            rec = self.env['bank.sms.transaction'].create(vals_2_create)
                            created_transactions.append(rec.name)
                        else:
                            continue
                        # fmt: on
            self.state = "done"
        except Exception as e:
            _logger.info(f"Error: {e}", exc_info=True)
            self.state = "processing"
        finally:
            name = self.name_get()[0][1]
            _logger.info(
                "transactions created from {} are: {}".format(
                    name, created_transactions
                )
            )

    def parse(self):
        self.ensure_one()
        self._parse()

    @api.model
    def _parse_transactions(self):
        bank_mails = self.search([("state", "=", "draft")])
        for bm in bank_mails:
            bm._parse()
