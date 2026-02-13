from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TaxInvoiceValidateConfirm(models.TransientModel):
    _name = "tax.invoice.validate.confirm"
    _description = "Confirm Tax Invoice Valid"

    # link to account.move
    tax_invoice_id = fields.Many2one("tax.invoice")
    account_move_ids = fields.Many2many("account.move", related="tax_invoice_id.account_move_ids")
    account_move_amount_untaxed = fields.Monetary(
        related="tax_invoice_id.account_move_total_untaxed_amount"
    )
    account_move_amount_total = fields.Monetary(related="tax_invoice_id.account_move_total_taxed_amount")

    total_amount_without_vat = fields.Monetary("Total Amount Without VAT", related="tax_invoice_id.total_amount_without_vat")
    total_amount_with_vat = fields.Monetary("Total Amount With VAT", related="tax_invoice_id.total_amount_with_vat")
    currency_id = fields.Many2one("res.currency", string="Currency")

    difference_amount_without_vat = fields.Monetary()
    difference_amount_with_vat = fields.Monetary()

    def button_set_validated(self):
        tax_invoice = self.env["tax.invoice"].browse(
            self._context.get("active_ids", [])
        )
        tax_invoice.set_validated()
        return {"type": "ir.actions.act_window_close"}
