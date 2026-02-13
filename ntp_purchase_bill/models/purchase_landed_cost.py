# __author__ = 'BinhTT'
from odoo import fields, models, api, _


class NTPPurchaseLandedCOst(models.TransientModel):
    _name = 'purchase.landed.cost'
    purchase_id = fields.Many2one('purchase.order')
    bill_id = fields.Many2one('account.move', 'Bill')
    total = fields.Float('Total')
    landed_costs_ids = fields.Many2many('stock.landed.cost', string='Landed Costs')
    had_landed_costs = fields.Boolean(string='Landed Costs')

    def create_landed_cost(self):
        return self.bill_id.button_create_landed_costs()

    def action_view_landed_costs(self):
        return self.bill_id.action_view_landed_costs()



class NTPPurchaseLandedCOstValuation(models.TransientModel):
    _name = 'purchase.landed.valuation'
    purchase_id = fields.Many2one('purchase.order')
    product_id = fields.Many2one('product.product', 'Product')
    qty = fields.Float('Qty')
    original_value = fields.Float('Original Value')
    new_value = fields.Float('New Value')
    additional_value = fields.Float('Additional Value')
    additional_unit_price = fields.Float('Additional Unit Cost')
    new_cost = fields.Float('New Unit Cost')
    unit_cost = fields.Float('Unit Cost')

