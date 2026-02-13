from odoo import fields, models, api, _


class TaxInvoiceResPartner(models.Model):
    _inherit = "res.partner"

    vendor_tax_invoices = fields.One2many("tax.invoice", "vendor_id")

    vendor_tax_invoices_count = fields.Integer(
        "Seller Tax Invoices Count",
        compute="_compute_vendor_tax_invoices_count",
        store=False,
    )

    auto_create_invoice_enable = fields.Boolean(
        "Auto Create Invoice Enable",
        default=False,
    )
    auto_create_invoice_type = fields.Selection(
        [("bill", "Vendor Bill"), ("receipt", "Purchase Receipt")],
        string="Bill/Receipt Creation",
        default="bill",
        required=True,
    )
    is_cost_aggregation = fields.Boolean("Cost Aggregation", default=False)
    aggregate_expense_account = fields.Many2one(
        "account.account", "Aggr. Expense Account"
    )
    aggregate_product = fields.Many2one("product.product", "Aggr. Product")
    collect_item_code_in_bill_ref = fields.Boolean(
        "Item Code In Bill Ref",
        default=False,
        help="When aggregate invoice lines of tax invoice to odoo bill,\
              may be item code is helpful to reconcile data. \
              Note: this setting is appliable for all invoice, not for only is_cost_aggregation=True",
    )

    @api.depends("vendor_tax_invoices")
    def _compute_vendor_tax_invoices_count(self):
        for res in self:
            res.vendor_tax_invoices_count = len(self.vendor_tax_invoices)

    def action_open_tax_invoice(self):
        context = self.env.context.copy()
        action = {
            "name": _("Tax Invoice"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "tax.invoice",
            "view_mode": "tree,form",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [("vendor_id", "=", self.id)],
            "target": "current",
        }
        return action
