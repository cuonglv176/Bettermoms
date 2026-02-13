from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    so_to_sliced_invoice_enable = fields.Boolean("Invoice Slicing")
    so_to_sliced_invoices_ids = fields.One2many(
        "so.to.sliced.invoices", "sale_order_id", "Slicing Invoice Policy"
    )
    so_to_sliced_invoice_start_date = fields.Date(
        "Invoice Start Date", default=lambda self: fields.Date.today()
    )
    company_group_code = fields.Many2one(
        "company.group", related="partner_id.company_group_code"
    )
    company_type = fields.Selection(related="partner_id.company_type")
    group_type = fields.Selection(related="partner_id.group_type")
    so_to_sliced_invoice_configurable = fields.Boolean(
        compute="_compute_so_to_sliced_invoice_configurable"
    )
    sub_ids = fields.One2many(related="partner_id.sub_ids")

    def _compute_so_to_sliced_invoice_configurable(self):
        for rec in self:
            rec.so_to_sliced_invoice_configurable = (
                rec.company_type == "group" and rec.group_type == "head"
            )

    def button_copy_default_slicing_config(self):
        self.ensure_one()
        self.so_to_sliced_invoices_ids.unlink()
        self.env["so.to.sliced.invoices"].copy_default_to_so(self.partner_id, self)
        self.message_post(
            body=f"copied default slicing invoice config from contact '{self.partner_id.name}' to sale order"
        )

    def write(self, vals):
        ret = super().write(vals)
        if len(self) == 1:
            if len(self.so_to_sliced_invoices_ids):
                if self.so_to_sliced_invoices_ids[-1].quota_unit != 'balance':
                    raise UserError("Quota Unit of last item of Invoice Slicing setting must be always 'balance'")
        return ret


class SaleOrderToMultipleInvoice(models.Model):
    _name = "so.to.sliced.invoices"
    _inherit = "so.to.sliced.invoices.base"

    sale_order_id = fields.Many2one("sale.order", "Sale Order", copy=False)

    def copy_default_to_so(self, partner_id, sale_order_id):
        self.env[self._name].search([("sale_order_id", "=", sale_order_id.id)]).unlink()
        data = []
        for line in self.env["so.to.sliced.invoices.default"].search(
            [("partner_id", "=", partner_id.id)]
        ):
            data += line.copy_data({"sale_order_id": sale_order_id.id})
        self.env[self._name].create(data)

    def write(self, vals):
        ret = super().write(vals)
        if "sale_order_id" in vals and vals["sale_order_id"] == False:
            for rec in self:
                rec.unlink()
        return ret
