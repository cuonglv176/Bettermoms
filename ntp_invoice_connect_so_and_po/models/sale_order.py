# __author__ = 'BinhTT'
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        res.update(sale_id=self.id)
        return res

    @api.depends('order_line.invoice_lines')
    def _get_invoiced(self):
        super()._get_invoiced()
        for order in self:
            invoices = self.env['account.move'].search([('sale_id', '=', order.id)])
            if invoices:
                order.invoice_ids += invoices
                order.invoice_count = len(order.invoice_ids)
        return

