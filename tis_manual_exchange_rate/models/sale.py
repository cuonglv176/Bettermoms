# -- coding: utf-8 --
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2021. All rights reserved.

from odoo import fields, api, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    company_currency_id = fields.Many2one('res.currency', string='Company Currency',
                                          default=lambda self: self.env.user.company_id.currency_id)
    is_apply_manual = fields.Boolean(default=False, string='Apply Manual Currency Exchange')
    exchange_rate = fields.Float(string='Manual Exchange Rate',
                                 help="rate of the currency to the company currency rate 1", digits=(16, 6))
    default_exchange_rate = fields.Float(string='Default Exchange Rate', digits=(16, 6))
    currency_flag = fields.Boolean(default=False, compute='get_currency_flag')

    @api.depends('currency_id')
    def get_currency_flag(self):
        for r in self:
            r.currency_flag = False
            if r.currency_id != r.company_currency_id:
                r.currency_flag = True

    @api.onchange('pricelist_id', 'date_order')
    def onchange_so_currency_id(self):
        print("hiii")
        if self.pricelist_id:
            if self.pricelist_id.currency_id != self.company_currency_id:

                self.currency_flag = True
                self.exchange_rate = self.currency_id.with_context(date=self.date_order).inverse_rate
                self.default_exchange_rate = self.currency_id.with_context(date=self.date_order).inverse_rate

                print("jjjjjjjjjjjj", self.currency_flag)
            else:
                self.currency_flag = False
                self.is_apply_manual = False
        else:
            self.currency_flag = False
            self.is_apply_manual = False

    def action_view_invoice(self):
        if self.currency_flag and self.exchange_rate > 0.0:
            context = self.env.context.copy()
            context.update({'from_sale': True, 'sale_exchange_rate': self.exchange_rate})
            self.env.context = context
        return super(SaleOrder, self).action_view_invoice()

    # @api.depends('pricelist_id')
    # def pricelist_currency(self):
    #     for data in self:
    #         if data.pricelist_id.currency_id:
    #             data.so_currency_id = data.pricelist_id.currency_id
    #         else:
    #             data.so_currency_id = data.currency_id

    @api.onchange('pricelist_id', 'currency_flag', 'is_apply_manual', 'exchange_rate')
    def onchange_exchange_rate(self):
        print("hhhhhhhhhhhhhhhhhhhhhh")
        for line in self.order_line:
            line.onchange_exchange_rate2()

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update({'exchange_rate': self.exchange_rate, 'is_apply_manual': self.is_apply_manual, 'default_exchange_rate': self.exchange_rate})

        return res


#
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_id')
    def onchange_exchange_rate2(self):
        print("jjj")
        if self.order_id.pricelist_id.currency_id != self.order_id.company_currency_id:
            if self.order_id.is_apply_manual and self.order_id.exchange_rate > 0.0:
                context = self.env.context.copy()
                context.update({'exchange_rate': self.order_id.exchange_rate})
                self.env.context = context

                converted_currency = self.currency_id._convert(self.product_id.lst_price,
                                                               self.order_id.pricelist_id.currency_id,
                                                               self.order_id.company_id, self.order_id.date_order)
                print(self.price_unit)
                self.price_unit = converted_currency
            else:
                print("calllllll")
                self.product_uom_change()

        else:
            print("here")
            self.product_uom_change()

    @api.onchange('product_uom_qty')
    def onchange_qty(self):
        print("44")
        self.onchange_exchange_rate2()


class Currency(models.Model):
    _inherit = "res.currency"

    def _convert(self, from_amount, to_currency, company, date, round=True):
        a = self.env.context.get('exchange_rate')
        last_price = True
        context = self.env.context.copy()
        context.update({'last_price': last_price})
        self.env.context = context
        if a:
            to_amount = from_amount * a
            return to_currency.round(to_amount)
        else:
            return super(Currency, self)._convert(from_amount, to_currency, company, date, round=True)
