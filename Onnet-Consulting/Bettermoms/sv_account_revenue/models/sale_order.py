# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = "sale.order"

    revenue_recognize_ids = fields.One2many('revenue.recognize', 'sale_order_id', string='Revenues')
    revenue_total = fields.Float(string='Total Revenue', compute='_compute_revenue_total')

    @api.depends('revenue_recognize_ids')
    def _compute_revenue_total(self):
        start_date = self.env.context.get('start_date', False)
        end_date = self.env.context.get('end_date', False)
        for order in self:
            revenue_total = 0
            for revenue in order.revenue_recognize_ids:
                if start_date and end_date:
                    if revenue.revenue_date >= datetime.strptime(start_date, '%Y-%m-%d').date()\
                            and revenue.revenue_date <= datetime.strptime(end_date, '%Y-%m-%d').date():
                        revenue_total += revenue.revenue
                else:
                    revenue_total += revenue.revenue

            order.revenue_total = revenue_total
