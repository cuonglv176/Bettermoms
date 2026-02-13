from odoo import api, models, fields, _


class EInvoiceSyncFromOdoo(models.TransientModel):
    _name = "ntp.einvoice.sync.from.odoo"
    _description = "Sync Invoice Data From Odoo To Create Invoice"

    einvoice_id = fields.Many2one("ntp.einvoice")
    update_product_label = fields.Boolean(default=True)
    update_buyer_info = fields.Boolean(default=True)
    update_invoice_monetary_data = fields.Boolean(default=True)

    def button_perform_update(self):
        if self.update_product_label:
            self.einvoice_id.button_update_invoice_line_label()
        if self.update_buyer_info:
            self.einvoice_id.button_update_buyer_info()
        if self.update_invoice_monetary_data:
            self.einvoice_id.button_update_invoice_info()
