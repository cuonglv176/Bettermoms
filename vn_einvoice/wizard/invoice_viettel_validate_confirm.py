from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InvoiceViettelValidateConfirm(models.TransientModel):
    _name = "invoice.viettel.validate.confirm"
    _description = "Confirm S-Invoice Valid"

    sinvoice_id = fields.Many2one("invoice.viettel")
    account_move_ids = fields.Many2many(
        "account.move",
        "Linked Customer Invoices",
        related="sinvoice_id.account_move_ids",
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency", related="sinvoice_id.currency_id"
    )

    total_amount_without_vat = fields.Integer(
        "Total Amount Without VAT", related="sinvoice_id.amount_untaxed"
    )
    total_amount_with_vat = fields.Integer(
        "Total Amount With VAT", related="sinvoice_id.amount_total"
    )

    invoice_total_amount_without_vat = fields.Monetary(
        "(Odoo Invoice) Total Amount Without VAT"
    )
    invoice_total_amount_with_vat = fields.Monetary(
        "(Odoo Invoice) Total Amount With VAT"
    )

    difference_amount_without_vat = fields.Monetary()
    difference_amount_with_vat = fields.Monetary()

    def button_set_validated(self):
        sinvoice = self.env["invoice.viettel"].browse(
            self._context.get("active_ids", [])
        )
        sinvoice.set_validated()
        return {"type": "ir.actions.act_window_close"}
