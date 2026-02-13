from odoo import models, fields, api, _

class EInvoiceCreate(models.TransientModel):
    _name = 'ntp.einvoice.create'
    _description = "EInvoice Create"

    account_move_id = fields.Many2one("account.move", "Invoice")
    company_id = fields.Many2one("res.company", related="account_move_id.company_id")
    einvoice_template_id = fields.Many2one("ntp.einvoice.template", "EInvoice Template")
    invoice_template = fields.Char("Invoice Template", related="einvoice_template_id.invoice_template")
    invoice_template_type = fields.Char("Invoice Template Type", related="einvoice_template_id.invoice_template_type")
    invoice_series = fields.Char("Invoice Series", related="einvoice_template_id.invoice_series")

    def button_create_einvoice(self):
        res = self.account_move_id.button_create_einvoice(self.einvoice_template_id)
        return res
