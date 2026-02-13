# __author__ = 'BinhTT'
from odoo import fields, api, models, _
from odoo.exceptions import UserError
from odoo.addons.purchase_stock.models.stock import StockMove
from odoo.tools.float_utils import float_round, float_is_zero

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    accounting_date = fields.Date('Accounting Date', help='Bill of lading date for International freight')
    currency_flag = fields.Boolean(default=False, compute='get_currency_flag')
    exchange_rate = fields.Float(string='Manual Exchange Rate',
                                 help="rate of the currency to the company currency rate 1", digits=(16, 6))
    default_exchange_rate = fields.Float(string='Default Exchange Rate', digits=(16, 6))

    currency_id = fields.Many2one('res.currency', compute='get_currency_flag')

    def get_currency_flag(self):
        self.currency_flag = False
        self.currency_id = self.env.company.currency_id
        move_obj = self.env['stock.move']
        if self.move_lines:
            move_obj = self.move_lines[0]
        if move_obj.purchase_line_id:
            self.currency_id = move_obj.purchase_line_id.currency_id
        if self.currency_id != self.env.company.currency_id:
            self.currency_flag = True

    @api.onchange('accounting_date')
    def onchange_accounting_date(self):
        if self.accounting_date:
            self.exchange_rate = self.currency_id.with_context(date=self.accounting_date).inverse_rate
            self.default_exchange_rate = self.currency_id.with_context(date=self.accounting_date).inverse_rate

    def update_price_unit(self):
        for move in self.move_lines:
            currency_price = (move.purchase_line_id and move.purchase_line_id.price_unit) or (move.sale_line_id and move.sale_line_id.price_unit)
            move.price_unit = self.exchange_rate * currency_price * (move.product_uom.factor / move.product_id.uom_id.factor)
        return


class NTPStockMoveEXC(models.Model):
    _inherit = 'stock.move'

    def _get_price_unit(self):
        """ Returns the unit price for the move"""
        self.ensure_one()
        if self.purchase_line_id and self.product_id.id == self.purchase_line_id.product_id.id:
            price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')
            line = self.purchase_line_id
            order = line.order_id
            price_unit = line.price_unit
            if line.taxes_id:
                qty = line.product_qty or 1
                price_unit = line.taxes_id.with_context(round=False).compute_all(price_unit, currency=line.order_id.currency_id, quantity=qty)['total_void']
                price_unit = float_round(price_unit / qty, precision_digits=price_unit_prec)
            if line.product_uom.id != line.product_id.uom_id.id:
                price_unit *= line.product_uom.factor / line.product_id.uom_id.factor
            if order.currency_id != order.company_id.currency_id:
                # The date must be today, and not the date of the move since the move move is still
                # in assigned state. However, the move date is the scheduled date until move is
                # done, then date of actual move processing. See:
                # https://github.com/odoo/odoo/blob/2f789b6863407e63f90b3a2d4cc3be09815f7002/addons/stock/models/stock_move.py#L36
                if self.picking_id.exchange_rate:
                    price_unit = price_unit * self.picking_id.exchange_rate
                else:
                    price_unit = order.currency_id._convert(
                        price_unit, order.company_id.currency_id, order.company_id, fields.Date.context_today(self),
                        round=False)
            return price_unit
        return super(StockMove, self)._get_price_unit()
