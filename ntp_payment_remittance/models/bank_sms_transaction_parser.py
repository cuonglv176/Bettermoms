from odoo import api, models, fields, tools


DEFAULT_TEMPLATE = """
#
# Require Template with following Value
# ACCOUNT / PAYMENT_TYPE / AMOUNT / AMOUNT_CURRENCY / BALANCE / BALANCE_CURRENCY / MESSAGE / DATE
#
"""


class BankSmsTransactionParser(models.Model):
    _name = "bank.sms.transaction.parser"
    _description = "Bank Sms Transaction Parser"

    name = fields.Char("Name")
    text_fsm = fields.Text("Text Fsm", default=DEFAULT_TEMPLATE.strip())
    bank_sms_ids = fields.Many2many("bank.sms")
