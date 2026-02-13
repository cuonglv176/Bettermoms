import re
import json
import pytz
import datetime
import dateutil
from io import StringIO
import email
import email.policy
from email.message import EmailMessage
from email import message_from_string, policy
from xmlrpc import client as xmlrpclib
from imaplib import IMAP4, IMAP4_SSL
import lxml
from lxml.html.clean import Cleaner

import logging
from typing import TYPE_CHECKING, Optional, Union
from odoo import api, models, fields, tools, _

from html.parser import HTMLParser

from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang


def get_cleaned_text(text):
    return re.sub(r"((\s+)?(\r)?\n(\s+)?)+", "\n", text)


def get_cleaned_body(body):
    cleaner = Cleaner()
    cleaner.javascript = True
    cleaner.style = True
    cleaner.inline_style = False
    cleaned_body = lxml.html.tostring(
        cleaner.clean_html(lxml.html.parse(StringIO(body)))
    )
    cleaned_body = cleaned_body.decode()
    return cleaned_body


class HTMLFilter(HTMLParser):
    """
    A simple no dependency HTML -> TEXT converter.
    Usage:
          str_output = HTMLFilter.convert_html_to_text(html_input)
    """

    def __init__(self, *args, **kwargs):
        self.text = ""
        self.in_body = False
        super().__init__(*args, **kwargs)

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag.lower() == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            self.text += data

    @classmethod
    def convert_html_to_text(cls, html: str) -> str:
        f = cls()
        f.feed(html)
        return f.text.strip()


"""

Refer: https://gist.github.com/martinrusev/6121028
https://datatracker.ietf.org/doc/html/rfc3501#section-6.4.4
"""


_logger = logging.getLogger(__name__)


class BankSms(models.Model):
    _name = "bank.sms"
    _description = "Bank Sms"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char("Name", default="/", copy=False)
    fetchmail_server_id = fields.Many2one(
        "fetchmail.server",
        "Inbound Mail Server",
        domain=[
            "&",
            ("state", "=", "done"),
            ("server_type", "=", "imap"),
        ],
        required=True,
        help="Fetchmail Server With Imap Protocol",
        copy=True,
    )
    journal_ids = fields.One2many(
        "account.journal",
        "bank_sms_id",
        "Journals",
        domain=[("type", "=", "bank")],
        copy=False,
    )
    bank_sms_aliases = fields.One2many(
        "bank.sms.alias", "bank_sms_id", "Account Aliases"
    )
    filter_from = fields.Char("From Address", required=True, copy=True)
    # currency_id = fields.Many2one("res.currency", string="Currency")
    state = fields.Selection(
        [
            ("draft", "Not Confirmed"),
            ("done", "Confirmed"),
        ],
        string="Status",
        index=True,
        readonly=True,
        copy=False,
        default="draft",
    )

    bank_sms_transaction_ids = fields.One2many("bank.sms.transaction", "bank_sms_id")
    bank_sms_mail_ids = fields.One2many("bank.sms.mail", "bank_sms_id")

    bank_sms_transaction_count = fields.Integer(compute="_compute_count_all")
    bank_sms_mail_count = fields.Integer(compute="_compute_count_all")

    last_fetch_server_side = fields.Date(
        "Last Fetch Server Date",
        # readonly=True,
        default=datetime.datetime.strptime("1970-01-01", "%Y-%m-%d").date(),
        copy=False,
    )
    last_fetch_server_side_str = fields.Char(
        compute="_compute_last_fetch_server_side_str", required=True, copy=False
    )
    last_fetch_server_search_result = fields.Text(copy=False)
    last_fetch_client_side = fields.Datetime("Last Fetch Date", copy=False)

    bank_sms_transaction_parser_ids = fields.Many2many(
        "bank.sms.transaction.parser", copy=True
    )
    auto_sync = fields.Boolean("Auto Sync to Journal", default=False)

    # @api.onchange('bank_sms_aliases')
    # def _on_change_bank_alias(self):
    #     self.last_fetch_server_search_result = False
    #     self.last_fetch_server_side = self.last_fetch_server_side.default

    def _compute_count_all(self):
        for rec in self:
            rec.bank_sms_transaction_count = len(rec.bank_sms_transaction_ids)
            rec.bank_sms_mail_count = len(rec.bank_sms_mail_ids)

    @api.depends("last_fetch_server_side")
    def _compute_last_fetch_server_side_str(self):
        for rec in self:
            rec.last_fetch_server_side_str = fields.Date.from_string(
                rec.last_fetch_server_side
            ).strftime("%d-%b-%Y")

    def action_set_confirm(self):
        self.ensure_one()
        self.state = "done"

    def action_set_draft(self):
        self.ensure_one()
        self.state = "draft"

    @api.model
    def _fetch_mails(self):
        """Method called by cron to fetch mails from servers"""
        bank_smss = self.search([("state", "=", "done")])
        for bc in bank_smss:
            bc.fetch_mail()

    def fetch_mail(self):
        """WARNING: meant for cron usage only  - DONT COMMIT ANY THING, JUST READ CONTENT"""
        server = self.fetchmail_server_id
        _logger.info(
            "start checking for emails on %s server %s for %s",
            server.server_type,
            server.name,
            self.journal_ids[0].name,
        )
        related, un_related = 0, 0
        imap_server: Optional[Union[IMAP4_SSL, IMAP4]] = None
        try:
            imap_server = server.connect()
            imap_server.select()
            last_fetch_server_side_str = self.last_fetch_server_side_str
            filter_from_addresses = self.filter_from.split(",")
            search_string = []
            for filter_from in filter_from_addresses:
                _search_string = "(FROM {} SINCE {})".format(
                    filter_from,
                    last_fetch_server_side_str,
                )
                search_string.append(_search_string)
            # https://stackoverflow.com/a/13196336
            search_string = " OR"*(len(filter_from_addresses) - 1) + " " +  " ".join(search_string)
            search_string = search_string.strip()
            _logger.info("Fetch mail: {}".format(search_string))
            __, data = imap_server.search(None, search_string)
            if last_fetch_server_side_str != "01-Jan-1970":  # only check if we synced 1
                if self.last_fetch_server_search_result != data[0].decode():
                    self.last_fetch_server_search_result = data[0].decode()
                else:
                    # skip process since last since result has same value
                    _logger.info(
                        "Exact same result with previous search, not fetching mail detail"
                    )
                    return
            else:
                self.last_fetch_server_search_result = data[0].decode()
            message_dict = {}
            for num in data[0].split():
                __, data = imap_server.fetch(num, "(RFC822)")
                message_dict = self.message_parse(data[0][1])
                if self._is_related_mail(message_dict):
                    related += 1
                    self._create_sms_mail(message_dict)
                else:
                    un_related += 1
                # always update this value so that in next call we dont need to fetch many mails
                self.last_fetch_server_side = message_dict["date"]
        except Exception:
            _logger.info(
                "General failure when trying to fetch mail from %s server %s for %s.",
                server.server_type,
                server.name,
                self.journal_ids[0].name,
                exc_info=True,
            )
        finally:
            _logger.info(
                "finish checking with %s related emails on %s server %s for %s",
                str(related),
                server.server_type,
                server.name,
                self.journal_ids[0].name,
            )
            self.last_fetch_client_side = fields.Datetime.now()
            if imap_server:
                imap_server.close()
                imap_server.logout()

    def _is_related_mail(self, message_dict):
        if self._find_journal_from_mail(message_dict):
            return True
        return False

    def _find_journal_from_mail(self, message_dict):
        self.ensure_one()
        for alias in self.bank_sms_aliases:
            if (
                alias.name in message_dict["subject"]
                or alias.name in message_dict["html_body"]
            ):
                return alias.journal_id
        return None

    def _create_sms_mail(self, message_dict):
        self.ensure_one()
        mail_records = self.env["bank.sms.mail"].search(
            [
                ("message_id", "=", message_dict["message_id"]),
                ("bank_sms_id", "=", self.id),
            ]
        )
        if not mail_records:
            vals_to_create = {
                "bank_sms_id": self.id,
                "message_id": message_dict["message_id"],
                "received_date": message_dict["date"],
                "from_address": message_dict["email_from"],
                "subject": message_dict["subject"],
                "html_body": message_dict["html_body"],
                "text_body": message_dict["text_body"],
                "cleaned_text_body": message_dict["cleaned_text_body"],
                "message_dict": json.dumps(message_dict),
            }
            self.env["bank.sms.mail"].create(vals_to_create)

    def message_parse(self, message):
        if isinstance(message, xmlrpclib.Binary):
            message = bytes(message.data)
        if isinstance(message, str):
            message = message.encode("utf-8")
        message = email.message_from_bytes(message, policy=email.policy.SMTP)
        msg_dict = {"message_type": "email"}
        message_id = message.get("Message-Id")
        msg_dict["message_id"] = message_id.strip()
        if message.get("Subject"):
            msg_dict["subject"] = tools.decode_message_header(message, "Subject")
        else:
            msg_dict["subject"] = ""
        email_from = tools.decode_message_header(message, "From")
        email_cc = tools.decode_message_header(message, "cc")
        email_from_list = tools.email_split_and_format(email_from)
        email_cc_list = tools.email_split_and_format(email_cc)
        msg_dict["email_from"] = email_from_list[0] if email_from_list else email_from
        msg_dict["from"] = msg_dict["email_from"]  # compatibility for message_new
        msg_dict["cc"] = ",".join(email_cc_list) if email_cc_list else email_cc
        msg_dict["recipients"] = ",".join(
            set(
                formatted_email
                for address in [
                    tools.decode_message_header(message, "Delivered-To"),
                    tools.decode_message_header(message, "To"),
                    tools.decode_message_header(message, "Cc"),
                    tools.decode_message_header(message, "Resent-To"),
                    tools.decode_message_header(message, "Resent-Cc"),
                ]
                if address
                for formatted_email in tools.email_split_and_format(address)
            )
        )
        msg_dict["to"] = ",".join(
            set(
                formatted_email
                for address in [
                    tools.decode_message_header(message, "Delivered-To"),
                    tools.decode_message_header(message, "To"),
                ]
                if address
                for formatted_email in tools.email_split_and_format(address)
            )
        )
        # compute references to find if email_message is a reply to an existing thread
        msg_dict["references"] = tools.decode_message_header(message, "References")
        msg_dict["in_reply_to"] = tools.decode_message_header(
            message, "In-Reply-To"
        ).strip()
        if message.get("Date"):
            try:
                date_hdr = tools.decode_message_header(message, "Date")
                parsed_date = dateutil.parser.parse(date_hdr, fuzzy=True)
                if parsed_date.utcoffset() is None:
                    # naive datetime, so we arbitrarily decide to make it
                    # UTC, there's no better choice. Should not happen,
                    # as RFC2822 requires timezone offset in Date headers.
                    stored_date = parsed_date.replace(tzinfo=pytz.utc)
                else:
                    stored_date = parsed_date.astimezone(tz=pytz.utc)
            except Exception:
                _logger.info(
                    "Failed to parse Date header %r in incoming mail "
                    "with message-id %r, assuming current date/time.",
                    message.get("Date"),
                    message_id,
                )
                stored_date = datetime.datetime.now()
            msg_dict["date"] = stored_date.strftime(
                tools.DEFAULT_SERVER_DATETIME_FORMAT
            )

        payload_dict = self._message_parse_extract_payload(message=message)
        msg_dict.update(payload_dict)
        return msg_dict

    def _message_parse_extract_payload(self, message):
        """Extract body as HTML from the mail message"""
        body = u""
        if message.get_content_maintype() == "text":
            encoding = message.get_content_charset()
            body = message.get_content()
            body = "<body>" + tools.ustr(body, encoding, errors="replace") + "</body>"
            if message.get_content_type() == "text/plain":
                # text/plain -> <pre/>
                body = tools.append_content_to_html(u"", body, preserve=True)
        else:
            alternative = False
            mixed = False
            html = u""
            for part in message.walk():
                if part.get_content_type() == "multipart/alternative":
                    alternative = True
                if part.get_content_type() == "multipart/mixed":
                    mixed = True
                if part.get_content_maintype() == "multipart":
                    continue  # skip container
                encoding = part.get_content_charset()  # None if attachment
                if part.get_content_type() == "text/plain" and (
                    not alternative or not body
                ):
                    body = tools.append_content_to_html(
                        body,
                        tools.ustr(part.get_content(), encoding, errors="replace"),
                        preserve=True,
                    )
                # 3) text/html -> raw
                elif part.get_content_type() == "text/html":
                    # mutlipart/alternative have one text and a html part, keep only the second
                    # mixed allows several html parts, append html content
                    append_content = not alternative or (html and mixed)
                    html = tools.ustr(part.get_content(), encoding, errors="replace")
                    if not append_content:
                        body = html
                    else:
                        body = tools.append_content_to_html(body, html, plaintext=False)
                    # we only strip_classes here everything else will be done in by html field of mail.message
                    body = tools.html_sanitize(
                        body, sanitize_tags=False, strip_classes=True
                    )
        text = HTMLFilter.convert_html_to_text(body)
        cleaned_text = get_cleaned_text(text)
        return {
            "html_body": get_cleaned_body(body),
            "text_body": text,
            "cleaned_text_body": cleaned_text,
        }

    def _get_alias_from_journal(self, journal):
        self.ensure_one()
        for alias in self.bank_sms_aliases:
            if alias.journal_id == journal:
                return alias
        return None

    def _fetch_transactions(self, journal):
        in_queue_transactions = self.bank_sms_transaction_ids.search(
            [
                ("journal_id", "=", journal.id),
                ("state", "=", "draft"),
            ],
            order="received_date",
            # limit=5
        )

        transactions = []
        for trx in in_queue_transactions:
            transactions.append(trx.convert_to_dict())

        alias = self._get_alias_from_journal(journal)

        # filling gap info between transactions
        gap_to_add = []
        for id, transaction in list(enumerate(transactions)):
            if id == 0:
                # check last sync transaction
                last_sync_transaction = self.env["bank.sms.transaction"].search(
                    [
                        ("state", "=", "posted"),
                        ("journal_id", "=", journal.id),
                    ],
                    order="received_date desc",
                    limit=1,
                )
                if last_sync_transaction:
                    gap = (
                        transaction["balance"]
                        - transaction["amount"]
                        - last_sync_transaction["balance"]
                    )
                else:
                    gap = 0
            else:
                gap = (
                    transaction["balance"]
                    - transaction["amount"]
                    - transactions[id - 1]["balance"]
                )
            if gap:
                gap_to_add.append(
                    [
                        id,
                        {
                            "date": transaction["date"],
                            "amount": gap,
                            "balance": transactions[id - 1]["balance"] + gap,
                            "payment_ref": "MISSING TRANSACTIONS - AMOUNT: {}".format(
                                formatLang(self.env, gap)
                            ),
                            "online_transaction_identifier": False,
                            "narration": "<b style='color: red'>GAP</b>",
                        },
                    ]
                )

        # add gap reversely
        for id, gap in sorted(gap_to_add, key=lambda x: x[0], reverse=True):
            transactions.insert(id, gap)

        # sync with bank statement
        self.env["account.bank.statement"].online_sync_sms_bank_statement(
            transactions, self, journal, alias.bank_account_type
        )
        in_queue_transactions.button_post()

    def get_balance(self, journal):
        try:
            return (
                self.env["bank.sms.transaction"]
                .search(
                    [("journal_id", "=", journal.id)],
                    order="received_date desc",
                    limit=1,
                )
                .balance
            )
        except:
            return 0


class BankAccountAlias(models.Model):
    _name = "bank.sms.alias"
    _description = "Bank Account Alias"

    _sql_constraints = [
        (
            "name_uniq",
            "UNIQUE (name)",
            "You can not have two alias with the same name !",
        ),
        (
            "journal_id_uniq",
            "UNIQUE (journal_id)",
            "You can not have two alias with the same journal_id !",
        ),
        (
            "name_journal_bank_sms_uniq",
            "UNIQUE (name, journal_id, bank_sms_id)",
            "Alias + Journal + Bank Sms must be unique !",
        ),
    ]

    name = fields.Char("Alias")
    journal_id = fields.Many2one(
        "account.journal",
        "Journal",
        domain=[("type", "=", "bank")],
    )
    bank_sms_id = fields.Many2one("bank.sms", "Bank Account")
    default_currency_id = fields.Many2one("res.currency", "Default Currency")
    # in case of credit card, all transaction is send money
    # so need to check this value to filling gap between transaction
    bank_account_type = fields.Selection(
        selection=[
            ("bank", "Bank Account"),
            ("credit_card", "Credit Card"),
            ("debit_card", "Debit Card"),
        ],
        default="bank",
        string="Account Type",
    )
