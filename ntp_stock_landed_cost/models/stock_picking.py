# __author__ = 'BinhTT'
from odoo import models, fields

class NTPStockPicking(models.Model):
    _inherit = 'stock.picking'

    def name_get(self):
        if self.env.context.get('vendor_bill_id', False):
            vendor_bill_id = self.env['account.move'].browse(self.env.context.get('vendor_bill_id', 0))
            if vendor_bill_id.invoice_line_ids.purchase_line_id.order_id.picking_ids or vendor_bill_id.purchase_order_id.picking_ids:
                self -= vendor_bill_id.invoice_line_ids.purchase_line_id.order_id.picking_ids
                self -= vendor_bill_id.purchase_order_id.picking_ids
                self = (vendor_bill_id.invoice_line_ids.purchase_line_id.order_id.picking_ids or vendor_bill_id.purchase_order_id.picking_ids) + self
        res = super().name_get()
        return res

    def search(self, args, offset=0, limit=None, order=None, count=False):
        res = super().search(args, offset, limit, order, count)
        if not count and self.env.context.get('vendor_bill_id', False):
            vendor_bill_id = self.env['account.move'].browse(self.env.context.get('vendor_bill_id', 0))
            if vendor_bill_id.invoice_line_ids.purchase_line_id.order_id.picking_ids or vendor_bill_id.purchase_order_id.picking_ids:
                res -= vendor_bill_id.invoice_line_ids.purchase_line_id.order_id.picking_ids
                res -= vendor_bill_id.purchase_order_id.picking_ids
                res = (vendor_bill_id.invoice_line_ids.purchase_line_id.order_id.picking_ids or vendor_bill_id.purchase_order_id.picking_ids) + res
        return res