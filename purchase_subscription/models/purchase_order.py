# __author__ = 'BinhTT'
import logging

from dateutil.relativedelta import relativedelta
from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class PurchaseSubsOrder(models.Model):
    _inherit = "purchase.order"

    purchase_subscription = fields.One2many('purchase.subscription', 'purchase_id')
    purchase_subscription_count = fields.Integer(compute='get_subscription_count')

    def action_view_subscription(self):
        subsciption_ids = self.mapped('purchase_subscription')
        action = self.env["ir.actions.actions"]._for_xml_id("purchase_subscription.purchase_subscription_action")
        if len(subsciption_ids) > 1:
            action['domain'] = [('id', 'in', subsciption_ids.ids)]
        elif len(subsciption_ids) == 1:
            form_view = [(self.env.ref('purchase_subscription.purchase_subscription_view_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = subsciption_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def get_subscription_count(self):
        self.purchase_subscription_count = len(self.purchase_subscription)

    def create_subscription(self):
        subscription_line = []
        vals = self.prepare_create_subscription()
        for line in self.order_line:
            subscription_line.append([0, 0, self.get_subscription_line(line)])
        vals.update(recurring_invoice_line_ids=subscription_line)
        subscription_id = self.env['purchase.subscription'].create(vals)
        return {
            'name': _('Purchase Subscription'),
            'view_mode': 'form',
            'res_model': 'purchase.subscription',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': subscription_id.id,
        }

    def get_subscription_line(self, line):
        data = {
            'product_id': line.product_id.id,
            'actual_quantity': line.product_qty,
            'uom_id': line.product_uom.id,
            'price_unit': line.price_unit,
            'name': line.name,
            'taxes_id': [[6, 0, line.taxes_id.ids]],
            "analytic_account_id": line.account_analytic_id.id,
            "analytic_tag_ids": [[6, 0, line.analytic_tag_ids.ids]],
        }
        return data

    def prepare_create_subscription(self):
        vals = {
            'partner_id': self.partner_id.id,
            'user_id': self.env.user.id,
            'code': self.name,
            'date_start': self.date_order,
            'recurring_next_date': self.date_order,
            'purchase_id': self.id,
            'currency_id': self.currency_id.id,
        }
        return vals