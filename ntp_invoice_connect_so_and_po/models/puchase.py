# __author__ = 'BinhTT'
# __author__ = 'BinhTT'
from odoo import models, fields, api, _
#
# class NTPPurchasesubscription(models.Model):
#     _inherit = "purchase.subscription"
#
#     def _compute_invoice_count(self):
#         """ Compute the number of invoices """
#         super()._compute_invoice_count
#         for sub in self:
#             sub.invoice_count = len(sub.invoice_ids)


class NTPPurchaseOrder(models.Model):
    _inherit = "purchase.order"
    invoice_ids = fields.Many2many('account.move', compute="_compute_invoice", string='Bills', copy=False, store=False)

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        res.update(purchase_order_id=self.id)
        return res

    @api.depends('order_line.invoice_lines.move_id')
    def _compute_invoice(self):
        super()._compute_invoice()
        for order in self:
            invoices = self.env['account.move'].search([('purchase_order_id', '=', order.id)])
            if invoices:
                order.invoice_ids += invoices
                order.invoice_count = len(order.invoice_ids)