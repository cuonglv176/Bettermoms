import re
import json
from odoo import api, models, fields, tools, _
from datetime import datetime

from odoo.exceptions import UserError


class BankSmsTransaction(models.Model):
    _name = "bank.sms.transaction"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Bank Sms Transaction"
    _order = "received_date desc"

    name = fields.Char("Name")
    journal_id = fields.Many2one("account.journal", "Journal", required=True)
    bank_sms_mail_id = fields.Many2one("bank.sms.mail", "Bank Sms Mail", required=True)
    bank_sms_id = fields.Many2one(
        related="bank_sms_mail_id.bank_sms_id", string="Bank Sms"
    )
    received_date = fields.Datetime(
        string="Date"
    )  # copy value from bank_sms_id.received_date
    payment_type = fields.Selection(
        [
            ("outbound", "Send Money"),
            ("inbound", "Receive Money"),
        ],
        string="Payment Type",
        # default="outbound",
        required=True,
    )
    amount = fields.Monetary("Amount")
    balance = fields.Monetary("Balance")
    message = fields.Char("Payment Message")
    currency_id = fields.Many2one("res.currency", "Currency")
    state = fields.Selection(
        [
            ("draft", "In Queue"),
            ("posted", "Synced"),
            ("skip", "Skipped"),
            ("error", "Error"),
        ],
        string="State",
        default="draft",
    )
    transaction_id = fields.Char("Transaction Id")
    signed_amount = fields.Monetary("Signed Amount", compute="_compute_signed_amount")

    def _compute_signed_amount(self):
        for rec in self:
            abs_amount = abs(rec.amount)
            if rec.payment_type == 'inbound':
                rec.signed_amount = abs_amount
            else:
                rec.signed_amount =  - abs_amount

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.received_date:
                rec.received_date = rec.bank_sms_mail_id.received_date
            rec.name = "BT/{}/{}".format(
                rec.id,
                rec.bank_sms_mail_id.received_date.strftime("%y-%b-%d").upper(),
            )
        return records

    def convert_to_dict(self):
        self.ensure_one()
        return {
            # "id": self.id,
            "online_transaction_identifier": self.transaction_id,
            "date": self.received_date,
            # 'date': self.received_date.strftime("%Y-%m-%d"),
            # "name": self.message,
            "amount": self.signed_amount,
            "payment_ref": self.message,
            # 'currency': self.currency_id.name,
            'balance': self.balance,
            # 'payment_type': self.payment_type,
        }

    def button_draft(self):
        for rec in self:
            rec.state = 'draft'

    def button_post(self):
        for rec in self:
            rec.state = 'posted'

    def button_skip(self):
        for rec in self:
            if rec.state in ['draft', 'skip']:
                rec.state = 'skip'
            else:
                raise UserError("Cannot change to 'Skip' from NON 'Draft'/'Skip' state")
