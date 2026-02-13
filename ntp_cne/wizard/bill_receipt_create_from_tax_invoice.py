from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BillReceiptCreationWizard(models.TransientModel):
    _name = "bill.receipt.from.tax.invoice"
    _description = "Bill Receipt Create From Tax Invoice"

    move_type = fields.Selection(
        [("in_invoice", "Vendor Bill"), ("in_receipt", "Purchase Receipt")],
        default="in_invoice",
    )

    def create_bill_receipt(self):
        tax_invoice = self.env["tax.invoice"].browse(
            self._context.get("active_ids", [])
        )
        action = tax_invoice.with_context(
            type=self.move_type
        ).action_create_bill_or_receipt()
        if self._context.get("open_bill_receipt"):
            return action
        return {"type": "ir.actions.act_window_close"}
