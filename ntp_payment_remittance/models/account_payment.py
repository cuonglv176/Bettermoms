from odoo import fields, models, api, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # bank_sms_transaction_id = fields.Many2one('bank.sms.transaction', "Bank Transaction")
