# -- coding: utf-8 --
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2021. All rights reserved.

from odoo import fields, api, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    company_currency_id = fields.Many2one('res.currency', string='Company Currency',
                                          default=lambda self: self.env.user.company_id.currency_id)
    is_apply_manual = fields.Boolean(default=False, string='Apply Manual Currency')
    exchange_rate = fields.Float(string='Manual Exchange Rate', help="rate of the currency to the company currency rate 1"
                                 , digits=(16, 6))
    default_exchange_rate = fields.Float(string='Default Exchange Rate', digits=(16, 6))
    currency_flag = fields.Boolean(default=False, compute='get_currency_flag')

    @api.depends('currency_id')
    def get_currency_flag(self):
        for r in self:
            r.currency_flag = False
            if r.currency_id != r.company_currency_id:
                r.currency_flag = True

    @api.onchange('exchange_rate')
    def onchange_po_exchange_rate(self):
        self.order_line._onchange_quantity()

    @api.onchange('currency_id', 'date_order')
    def onchange_currency_id_flag(self):
        if self.currency_id != self.company_currency_id:
            self.currency_flag = True
            self.exchange_rate = self.currency_id.with_context(date=self.date_order).inverse_rate
            self.default_exchange_rate = self.currency_id.with_context(date=self.date_order).inverse_rate
        else:
            self.currency_flag = False
            self.exchange_rate = 0.0

    def action_create_invoice(self):
        if len(self) == 1 and self.currency_flag and self.exchange_rate > 0.0:
            context = self.env.context.copy()
            context.update({'bill_rate': self.exchange_rate})
            self.env.context = context
            print('self.env.context', self.env.context)
        return super(PurchaseOrder, self).action_create_invoice()

    def _prepare_invoice(self):
        res = super(PurchaseOrder, self)._prepare_invoice()
        if self.currency_flag and self.exchange_rate > 0.0:
            res.update({'is_apply_manual': self.is_apply_manual, 'exchange_rate': self.exchange_rate,
                        'default_exchange_rate': self.exchange_rate})
        return res
    def _prepare_picking(self):
        res = super(PurchaseOrder, self)._prepare_picking()
        if self.currency_flag:
            res.update({
                        'default_exchange_rate': self.exchange_rate or self.currency_id.with_context(date=self.date_order).inverse_rate,
                        'exchange_rate': self.exchange_rate or self.currency_id.with_context(date=self.date_order).inverse_rate,
                        'accounting_date': self.date_order})
        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # def find_price_unit(self):
    #     print("innnnnnnnnnnnnnnn")
    #     if not self.product_id:
    #         return
    #     params = {'order_id': self.order_id}
    #     seller = self.product_id._select_seller(
    #         partner_id=self.partner_id,
    #         quantity=self.product_qty,
    #         date=self.order_id.date_order and self.order_id.date_order.date(),
    #         uom_id=self.product_uom,
    #         params=params)
    #
    #     if seller or not self.date_planned:
    #         self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #
    #     if not seller:
    #         if self.product_id.seller_ids.filtered(lambda s: s.name.id == self.partner_id.id):
    #             self.price_unit = 0.0
    #         print("returrr")
    #         return
    #
    #     price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price,
    #                                                                          self.product_id.supplier_taxes_id,
    #                                                                          self.taxes_id,
    #                                                                          self.company_id) if seller else 0.0
    #     print("price___", price_unit)
    #     return price_unit

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if self.order_id.currency_flag and self.order_id.exchange_rate > 0.0:
            context = self.env.context.copy()
            context.update({'purchase_currency_rate': self.order_id.exchange_rate})
            self.env.context = context
            print('self.env.context', self.env.context)

        return super(PurchaseOrderLine, self)._onchange_quantity()
