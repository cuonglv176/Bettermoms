from odoo import api, models, fields, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    so_to_sliced_invoice_enable = fields.Boolean("Invoice Slicing")
    so_to_sliced_invoices_ids = fields.One2many(
        "so.to.sliced.invoices.default", "partner_id", "Slicing Invoice Policy"
    )

    def write(self, vals):
        ret = super().write(vals)
        if len(self) == 1:
            if len(self.so_to_sliced_invoices_ids):
                if self.so_to_sliced_invoices_ids[-1].quota_unit != 'balance':
                    raise UserError("Quota Unit of last item of Invoice Slicing setting must be always 'balance'")
        return ret


class SaleOrderToSlicedInvoicesDefault(models.Model):
    _name = "so.to.sliced.invoices.default"
    _inherit = "so.to.sliced.invoices.base"

    def write(self, vals):
        ret = super().write(vals)
        if "partner_id" in vals and vals["partner_id"] == False:
            for rec in self:
                rec.unlink()
        return ret
