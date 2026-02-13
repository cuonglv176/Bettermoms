# -- coding: utf-8 --
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2021. All rights reserved.

from odoo import fields, api, models, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    default_exchange_rate = fields.Float(string='Default Exchange Rate', digits=(16, 6), readonly=1)
    exchange_rate = fields.Float(string='Manual Exchange Rate',
                                 help="rate of the currency to the company currency rate 1", digits=(16, 6), readonly=1)

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    exchange_amount = fields.Float(string='Amount', digits=(16, 6))
    is_apply_manual = fields.Boolean(string='Apply Manual Currency Exchange')
    exchange_rate = fields.Float(string='Manual Exchange Rate',
                                 help="rate of the currency to the company currency rate 1", digits=(16, 6))
    currency_flag = fields.Boolean(default=False, compute='get_currency_flag')
    default_exchange_rate = fields.Float(string='Default Exchange Rate', digits=(16, 6))


    @api.depends('currency_id')
    def get_currency_flag(self):
        for r in self:
            r.currency_flag = False
            if r.currency_id != r.company_currency_id:
                r.currency_flag = True

    @api.onchange('journal_id')
    def onchange_payment_amount(self):
        if self.env.context.get('active_id', False):
            invoice = self.env['account.move'].browse(self.env.context['active_id'])
            self.is_apply_manual = invoice.is_apply_manual
            self.exchange_rate = invoice.exchange_rate
            self.default_exchange_rate = invoice.default_exchange_rate

    @api.onchange('exchange_rate')
    def _onchange_payment_exchange_rate(self):
        print("hey")
        if self.env.context.get('active_id', False):
            invoice = self.env['account.move'].browse(self.env.context.get('active_id'))
            if invoice.exchange_rate != self.exchange_rate:
                self.amount = invoice.amount_total_signed * self.exchange_rate

    def _create_payment_vals_from_wizard(self):
        res = super()._create_payment_vals_from_wizard()
        if self.env.context.get('active_id', False) and self.currency_flag:
            invoice = self.env['account.move'].browse(self.env.context.get('active_id'))
            res.update(exchange_rate=invoice.exchange_rate, default_exchange_rate=invoice.default_exchange_rate)
        return res

    def _post_payments(self, to_process, edit_mode=False):
        ctx = self.env.context.copy()
        if self.env.context.get('active_id', False) and self.currency_flag:
            invoice = self.env['account.move'].browse(self.env.context.get('active_id'))
            ctx.update(exchange_rate=invoice.exchange_rate, default_exchange_rate=invoice.default_exchange_rate)
        res = super(AccountPaymentRegister, self.with_context(ctx))._post_payments(to_process, edit_mode)
        return res

    def _init_payments(self, to_process, edit_mode=False):
        ctx = self.env.context.copy()
        if self.env.context.get('active_id', False) and self.currency_flag:
            invoice = self.env['account.move'].browse(self.env.context.get('active_id'))
            ctx.update(exchange_rate=invoice.exchange_rate, default_exchange_rate=invoice.default_exchange_rate, bill_rate=invoice.exchange_rate)
        res = super(AccountPaymentRegister, self.with_context(ctx))._init_payments(to_process, edit_mode)
        return res
