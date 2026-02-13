# __author__ = 'BinhTT'
from odoo import models, fields, api, _


class NTPAccountMove(models.Model):
    _inherit = "account.move"

    purchase_order_id = fields.Many2one('purchase.order', readonly=True,
                                  string='Purchase Order', states={'draft': [('readonly', False)]},
                                  help="Auto-complete from a past Purchase order.")
    sale_id = fields.Many2one('sale.order', readonly=True,
                                  string='Sale Order', states={'draft': [('readonly', False)]},
                                  help="Auto-complete from a past Sale order.")

    purchase_subscription_id = fields.Many2one("purchase.subscription", string="Purchase Subscription")


    def write(self, vals):
        if 'purchase_subscription_id' in vals:
            subscription_id = self.env['purchase.subscription'].browse(vals.get('purchase_subscription_id'))
            subscription_id.invoice_ids = [(4, self.id)]

        if 'purchase_order_id' in vals:
            purchase_obj = self.env['purchase.order'].browse(vals.get('purchase_order_id'))
            purchase_obj.invoice_ids = [(4, self.id)]
            for line in purchase_obj.order_line:
                if self.invoice_line_ids.filtered(lambda x:x.product_id == line.product_id):
                    purchase_obj.order_line.invoice_lines += self.invoice_line_ids.filtered(lambda x:x.product_id == line.product_id)
        return super().write(vals)

    @api.model
    def create(self, vals):
        res = super().create(vals)
        if 'purchase_subscription_id' in vals:
            subscription_id = self.env['purchase.subscription'].browse(vals.get('purchase_subscription_id'))
            subscription_id.invoice_ids = [(4, self.id)]

        if 'purchase_order_id' in vals:
            purchase_obj = self.env['purchase.order'].browse(vals.get('purchase_order_id'))
            purchase_obj.invoice_ids = [(4, self.id)]
            for line in purchase_obj.order_line:
                if res.invoice_line_ids.filtered(lambda x:x.product_id == line.product_id):
                    purchase_obj.order_line.invoice_lines += res.invoice_line_ids.filtered(lambda x:x.product_id == line.product_id)
        return res