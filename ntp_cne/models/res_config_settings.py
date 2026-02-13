from odoo import models, fields, api


class TaxInvoiceConfig(models.TransientModel):
    _inherit = "res.config.settings"

    tax_invoice_bizzi_api_url = fields.Char("Bizzi API URL")
    tax_invoice_bizzi_api_key = fields.Char("Bizzi X-API-KEY")
    tax_invoice_bizzi_view_url = fields.Char("Bizzi View URL")

    @api.model
    def get_values(self):
        res = super(TaxInvoiceConfig, self).get_values()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        res.update(
            tax_invoice_bizzi_api_url=get_param(
                "tax_invoice.tax_invoice_bizzi_api_url"
            ),
            tax_invoice_bizzi_api_key=get_param(
                "tax_invoice.tax_invoice_bizzi_api_key"
            ),
            tax_invoice_bizzi_view_url=get_param(
                "tax_invoice.tax_invoice_bizzi_view_url"
            ),
        )
        return res

    def set_values(self):
        super(TaxInvoiceConfig, self).set_values()
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param(
            "tax_invoice.tax_invoice_bizzi_api_url", self.tax_invoice_bizzi_api_url
        )
        set_param(
            "tax_invoice.tax_invoice_bizzi_api_key", self.tax_invoice_bizzi_api_key
        )
        set_param(
            "tax_invoice.tax_invoice_bizzi_view_url", self.tax_invoice_bizzi_view_url
        )
        # # synchronize the bizzi invoice for temporary here
        # # need to provide external button for manual sync
        # self.env['tax.invoice'].sync_tax_invoice()
