# __author__ = 'BinhTT'
from odoo import fields, api, models


class NTPSalePaymentStatus(models.TransientModel):
    _name = 'sale.payment.status'

    date = fields.Date('Date')
    late_due = fields.Float('Late Due')
    amount_due = fields.Float('Amount Due')
    amount_due_balance = fields.Float('Amount Due Balance')
    paid_amount = fields.Float('Paid Amount')
    order_id = fields.Many2one('sale.order')
    today = fields.Boolean()