# -- coding: utf-8 --
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2021. All rights reserved.

from odoo import fields, api, models, _


class Currency(models.Model):
    _inherit = "res.currency"

    def _convert(self, from_amount, to_currency, company, date, round=True):
        print("From-amount", from_amount)
        print("curr-context", self.env.context)
        if self == to_currency:
            return super(Currency, self)._convert(from_amount, to_currency, company, date, round=round)
        if self.env.context.get('no_conversion'):
            if self.env.context['no_conversion']:
                return from_amount
        if 'tax_conversion' in self.env.context:
            if 'manual_currency_tax' in self.env.context:
                from_amount = from_amount * self.env.context.get('manual_currency_tax')
                print("from_amount_tax", from_amount)
                return from_amount
            else:
                return super(Currency, self)._convert(from_amount, to_currency, company, date, round=True)
        if 'convert_journal' in self.env.context:
            if 'manual_currency_journal' in self.env.context:
                from_amount = from_amount * self.env.context.get('manual_currency_journal')
                print("from_amount3", from_amount)
                return from_amount
            else:
                return super(Currency, self)._convert(from_amount, to_currency, company, date, round=True)
        # if 'from_sale' in self.env.context:
        #     if self.env.context.get('sale_exchange_rate'):
        #         from_amount = from_amount / self.env.context.get('sale_exchange_rate')
        #         print("from-saleeeeeeeeee")
        #         return from_amount
        if self.env.context.get('bill_rate'):
            from_amount = from_amount * self.env.context.get('bill_rate')
            return from_amount
        if 'active_model' in self.env.context:
            if self.env.context['active_model'] == 'sale.order':
                if self.env.context.get('active_id'):
                    sale_order = self.env['sale.order'].browse(self._context.get('active_id'))
                    if sale_order.is_apply_manual and sale_order.exchange_rate > 0.0:
                        from_amount = from_amount * sale_order.exchange_rate
                        print("ssaaaaaaaaaaaa", from_amount)
                        return from_amount
                    else:
                        return from_amount
                else:
                    return from_amount
            else:
                return from_amount

        if self.env.context.get('purchase_currency_rate'):
            print("purchase_currency_rate-----------------",from_amount)
            from_amount = from_amount * self.env.context.get('purchase_currency_rate')
            return from_amount

        if self.env.context.get('currency_exchange_post'):
            from_amount = from_amount * self.env.context.get('exchange_rate')
            return from_amount

        else:
            return super(Currency, self)._convert(from_amount, to_currency, company, date, round=round)
