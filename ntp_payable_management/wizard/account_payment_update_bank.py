from odoo import models, fields, api


class AccountPaymentUpdateBank(models.TransientModel):
    _name = "account.payment.update.bank"
    _description = "Update Bank In Payment"

    payment_id = fields.Many2one("account.payment")
    partner_id = fields.Many2one("res.partner", related="payment_id.partner_id")
    partner_bank_id = fields.Many2one("res.partner.bank", domain="[('partner_id', '=', partner_id)]")

    def button_update(self):
        self.payment_id.partner_bank_id = self.partner_bank_id
