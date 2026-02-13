from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    tax_invoice_ids = fields.Many2many("tax.invoice")
    tax_invoices_count = fields.Integer(
        "Seller Tax Invoices Count",
        compute="_compute_tax_invoices_count",
        store=False,
    )
    is_product_missing = fields.Boolean(
        compute="_compute_is_product_missing", store=False
    )
    issue_date_tax_invoice = fields.Date(compute="_compute_issue_date_tax_invoice")

    def _compute_issue_date_tax_invoice(self):
        for rec in self:
            rec.issue_date_tax_invoice = False
            if rec.tax_invoice_ids and len(rec.tax_invoice_ids) == 1:
                try:
                    tax_invoice = rec.tax_invoice_ids[0]
                    rec.issue_date_tax_invoice = tax_invoice.get_strftime_with_user_tz(
                        tax_invoice.issued_date
                    )
                except:
                    pass

    def _compute_is_product_missing(self):
        for rec in self:
            rec.is_product_missing = False
            if rec.invoice_line_ids:
                for line in rec.invoice_line_ids:
                    if not line.product_id:
                        rec.is_product_missing = True
                        break

    def button_find_product_from_label(self):
        self.ensure_one()
        active_labels = self.env["product.label.in.tax.invoice"].search(
            [("status", "=", True)], order="priority desc"
        )
        for line in self.invoice_line_ids:
            if line.product_id:
                continue
            matched_labels = active_labels.filtered(
                lambda x: x.is_match(line.name)
                and self.partner_id in x.product_id.seller_ids.mapped("name")
            )
            if matched_labels:
                line.product_id = matched_labels.product_id
                line.product_uom_id = line._get_computed_uom()
                line._onchange_product_id()

    @api.depends("tax_invoice_ids")
    def _compute_tax_invoices_count(self):
        for res in self:
            res.tax_invoices_count = len(res.tax_invoice_ids)

    def action_open_tax_invoice(self):
        context = self.env.context.copy()
        action = {
            "name": _("Tax Invoice"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "tax.invoice",
            "view_mode": "tree,form",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [("id", "in", self.tax_invoice_ids.ids)],
            "context": {"create": False},
            "target": "current",
        }
        return action

    def task_replace_text_in_ref(self):
        bills = self.env['account.move'].sudo().search([('tax_invoice_ids', '!=', False)])
        for bill in bills:
            if bill.ref:
                TO_REMOVE = ["HÓA ĐƠN GIÁ TRỊ GIA TĂNG", "Hóa đơn giá trị gia tăng"]
                for k in TO_REMOVE:
                    bill.ref = bill.ref.replace(k, "").strip().replace("  ", " ")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Apply lock for price unit, taxes and name
    # for accounting, it will follow product config
    is_locked = fields.Boolean("Locked", default=False)

    def _get_computed_price_unit(self):
        if self.is_locked:
            return self.price_unit
        super(AccountMoveLine, self)._get_computed_price_unit()

    def _get_computed_taxes(self):
        if self.is_locked:
            return self.tax_ids
        super(AccountMoveLine, self)._get_computed_taxes()

    def _get_computed_name(self):
        if self.is_locked and self.name:
            return self.name
        super(AccountMoveLine, self)._get_computed_name()
