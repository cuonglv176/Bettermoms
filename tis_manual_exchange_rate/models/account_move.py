# -- coding: utf-8 --
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2021. All rights reserved.

from odoo import fields, api, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def default_tax_calculation_rounding_method(self):
        return self.env.company.tax_calculation_rounding_method

    is_apply_manual = fields.Boolean(default=False, string='Apply Manual Currency')
    company_currency_id = fields.Many2one('res.currency', string='Company Currency',
                                          default=lambda self: self.env.user.company_id.currency_id)
    default_exchange_rate = fields.Float(string='Default Exchange Rate', digits=(16, 6))
    tax_exchange_rate = fields.Float(string='Tax Exchange Rate', digits=(16, 6))
    exchange_rate = fields.Float(string='Manual Exchange Rate',
                                 help="rate of the currency to the company currency rate 1", digits=(16, 6))
    currency_flag = fields.Boolean(default=False, compute='get_currency_flag')
    tax_exchange_rate_flag = fields.Boolean(default=False, )
    bank_total_amount = fields.Float('Bank Total Amount', help='VND per Unit')
    tax_calculation_rounding_method = fields.Selection([
        ('round_per_line', 'Round per Line'),
        ('round_globally', 'Round Globally'),
    ], default=default_tax_calculation_rounding_method, string='Tax Calculation Rounding Method', )

    @api.onchange('tax_exchange_rate')
    def onchange_tax_exchange_rate(self):
        if self.tax_exchange_rate != self.exchange_rate:
            self.tax_exchange_rate_flag = True
        else:
            self.tax_exchange_rate_flag = False
        return self.change_price_unit()

    @api.onchange('bank_total_amount')
    def onchange_bank_total_amount(self):
        if self.bank_total_amount:
            self.exchange_rate = self.bank_total_amount / self.amount_total
            if not self.tax_exchange_rate_flag:
               self.tax_exchange_rate = self.exchange_rate
            self.change_price_unit()
        return

    @api.depends('currency_id')
    def get_currency_flag(self):
        for r in self:
            r.currency_flag = False
            if r.currency_id != r.company_currency_id:
                r.currency_flag = True

    @api.onchange('currency_id', 'date')
    def onchange_so_currency_id(self):
        print("hiii")
        if self.currency_id:
            if self.currency_id != self.company_currency_id:
                self.currency_flag = True
                self.is_apply_manual = True
                self.default_exchange_rate = self.currency_id.with_context(date=self.date).inverse_rate
                self.exchange_rate = self.currency_id.with_context(date=self.date).inverse_rate
                self.tax_exchange_rate = self.currency_id.with_context(date=self.date).inverse_rate

            else:
                self.currency_flag = False
                self.is_apply_manual = False
                self.exchange_rate = 0.0
                self.default_exchange_rate = 0.0
                self.tax_exchange_rate = 0.0
                # for line in self.invoice_line_ids:
                #     line._onchange_product_id()
                #     line._onchange_amount_currency()
                # print("lll", self.currency_flag)
            self.change_price_unit()

    def _recompute_tax_lines(self, recompute_tax_base_amount=False):
        if self.currency_flag and self.tax_exchange_rate > 0.0:
            context = self.env.context.copy()
            if context.get('no_conversion'):
                context['no_conversion'] = False
            else:
                context['no_conversion'] = False
            context.update({'tax_conversion': True, 'manual_currency_tax': self.tax_exchange_rate or self.exchange_rate})
            self.env.context = context
            return super(AccountMove, self.with_context(context))._recompute_tax_lines(recompute_tax_base_amount=False)
        return super(AccountMove, self)._recompute_tax_lines(recompute_tax_base_amount=False)

    @api.onchange('is_apply_manual', 'exchange_rate', 'tax_calculation_rounding_method')
    def change_price_unit(self):
        if self.currency_flag and self.exchange_rate > 0.0:
            print("in-change_price_unit", self.env.context)
            ctx = self.env.context.copy()
            round_tax = False if self.tax_calculation_rounding_method == 'round_globally' else True

            ctx.update(manual_currency_journal=self.exchange_rate, manual_currency_tax=self.tax_exchange_rate, round=round_tax)
            self = self.with_context(ctx)
            if not self.env.context.get('create_bill'):

                for line in self.invoice_line_ids:
                    line._onchange_product_id()
                    line._onchange_amount_currency()
                    line._onchange_price_subtotal()
                    self._recompute_dynamic_lines()
                    self.with_context(manual_currency_tax=self.tax_exchange_rate, tax_conversion=True,round=round_tax)._recompute_tax_lines()

                    print("called")
            total_credit = sum(self.line_ids.mapped('credit'))
            total_debit = sum(self.line_ids.mapped('debit'))
            if total_debit != total_credit:
                if self.move_type == 'out_invoice':
                    account_receivable = self.line_ids.filtered(
                        lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                    account_receivable.debit = total_credit
                elif self.move_type == 'in_invoice':
                    account_payable = self.line_ids.filtered(
                        lambda x: x.account_id == self.partner_id.property_account_payable_id)
                    if account_payable:
                        account_payable.credit = total_debit

    def action_post(self):
        print("<<", self.purchase_id, self.env.context)
        if self.currency_flag and self.exchange_rate > 0.0:
            context = self.env.context.copy()
            context.update({'currency_exchange_post': True, 'exchange_rate': self.exchange_rate})
            self.env.context = context

        # if not self.env.context.get('active_model') == 'sale.order' and not self.env.context.get(
        #         'active_model') == 'purchase.order':
        #     if self.is_apply_manual and self.exchange_rate > 0.0:
        #         print("hereeeeee?")
        #         for line in self.invoice_line_ids:
        #             line._onchange_product_id()
        #             line._onchange_amount_currency()
        return super(AccountMove, self).action_post()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_computed_price_unit(self):
        res = super(AccountMoveLine, self)._get_computed_price_unit()
        print(">>>>", res)

        if self.move_id.currency_flag and self.move_id.exchange_rate > 0.0:
            product_price_unit = self.compute_price_unit() * self.move_id.exchange_rate

            # self.price_unit = product_price_unit
            print("*******", product_price_unit)
            res = product_price_unit
            if self.env.context.get('skip_compute_price', False):
                res = self.price_unit
                    # return product_price_unit
            # else:
            #     print(self, "<<<<<<<")
            #     self.price_unit = self._onchange_product_id()

        else:
            self.price_unit = res
        print("Final", res)
        return res

    # @api.onchange('product_id')
    # def onchange_product_id_currency_rate(self):
    #     if self.move_id.is_apply_manual and self.move_id.exchange_rate > 0.0:
    #         print("here")
    #         self._get_computed_price_unit()
    #     else:
    #         self._onchange_product_id()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # res = super(AccountMoveLine, self)._onchange_product_id()
        if self.move_id.currency_flag and self.move_id.exchange_rate > 0.0:
            context = self.env.context.copy()
            context.update({'no_conversion': True, 'manual_currency': self.move_id.exchange_rate,  'skip_compute_price': True})
            self.env.context = context
            print("CONTEX", self.env.context)
        return super(AccountMoveLine, self)._onchange_product_id()

    # @api.model
    # def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes,
    #                                         move_type):
    #     context = self.env.context.copy()
    #     if self.move_id.is_apply_manual and self.move_id.exchange_rate > 0.0:
    #         context.update({'manual_currency_rate': self.move_id.exchange_rate})
    #         self.env.context = context
    #         print("CONTEX", self.env.context)
    #     return super(AccountMoveLine, self)._get_price_total_and_subtotal_model(price_unit, quantity, discount,
    #                                                                             currency, product, partner, taxes,
    #                                                                             move_type)

    def compute_price_unit(self):
        self.ensure_one()
        if self.env.context.get('skip_compute_price', False):
            return self.price_unit
        if not self.product_id:
            return self.price_unit
        elif self.move_id.is_sale_document(include_receipts=True):
            # Out invoice.
            price_unit = self.product_id.lst_price
        elif self.move_id.is_purchase_document(include_receipts=True):
            # In invoice.
            price_unit = self.product_id.standard_price
        else:
            return self.price_unit

        if self.product_uom_id != self.product_id.uom_id:
            price_unit = self.product_id.uom_id._compute_price(price_unit, self.product_uom_id)
        print(">>>>>price-unit", price_unit)
        return price_unit

    @api.onchange('product_uom_id')
    def _onchange_uom_id(self):
        res = super(AccountMoveLine, self)._onchange_uom_id()
        if self.move_id.currency_flag and self.move_id.exchange_rate > 0.0:
            self.price_unit = self._get_computed_price_unit()
        return res

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        if self.move_id.currency_flag and self.move_id.exchange_rate > 0.0:
            context = self.env.context.copy()
            if context.get('no_conversion'):
                context['no_conversion'] = False
            else:
                context['no_conversion'] = False

            context.update({'convert_journal': True, 'manual_currency_journal': self.move_id.exchange_rate})
            self.env.context = context
            print("CONTEX", self.env.context)
        return super(AccountMoveLine, self)._onchange_amount_currency()

    @api.onchange('quantity', 'discount', 'price_unit', 'tax_ids')
    def _onchange_price_subtotal(self):
        context = self.env.context.copy()
        if self.move_id.currency_flag and self.move_id.exchange_rate > 0.0:

            if context.get('no_conversion'):
                context['no_conversion'] = False
            else:
                context['no_conversion'] = False
            context.update({'convert_journal': True, 'manual_currency_journal': self.move_id.exchange_rate})
            self.env.context = context
            print("CONTEX", self.env.context)
        return super(AccountMoveLine, self.with_context(context))._onchange_price_subtotal()

    def _get_computed_taxes(self):

        self.ensure_one()
        if self.env.context.get('skip_compute_price', False):
            return self.tax_ids
        return super(AccountMoveLine, self)._get_computed_taxes()


    def _prepare_reconciliation_partials(self):
        ''' Prepare the partials on the current journal items to perform the reconciliation.
        /!\ The order of records in self is important because the journal items will be reconciled using this order.

        :return: A recordset of account.partial.reconcile.
        '''
        def fix_remaining_cent(currency, abs_residual, partial_amount):
            if abs_residual - currency.rounding <= partial_amount <= abs_residual + currency.rounding:
                return abs_residual
            else:
                return partial_amount

        debit_lines = iter(self.filtered(lambda line: line.balance > 0.0 or line.amount_currency > 0.0))
        credit_lines = iter(self.filtered(lambda line: line.balance < 0.0 or line.amount_currency < 0.0))
        debit_line = None
        credit_line = None

        debit_amount_residual = 0.0
        debit_amount_residual_currency = 0.0
        credit_amount_residual = 0.0
        credit_amount_residual_currency = 0.0
        debit_line_currency = None
        credit_line_currency = None
        partials_vals_list = []

        while True:

            # Move to the next available debit line.
            if not debit_line:
                debit_line = next(debit_lines, None)
                if not debit_line:
                    break
                debit_amount_residual = debit_line.amount_residual

                if debit_line.currency_id:
                    debit_amount_residual_currency = debit_line.amount_residual_currency
                    debit_line_currency = debit_line.currency_id
                else:
                    debit_amount_residual_currency = debit_amount_residual
                    debit_line_currency = debit_line.company_currency_id

            # Move to the next available credit line.
            if not credit_line:
                credit_line = next(credit_lines, None)
                if not credit_line:
                    break
                credit_amount_residual = credit_line.amount_residual

                if credit_line.currency_id:
                    credit_amount_residual_currency = credit_line.amount_residual_currency
                    credit_line_currency = credit_line.currency_id
                else:
                    credit_amount_residual_currency = credit_amount_residual
                    credit_line_currency = credit_line.company_currency_id

            min_amount_residual = min(debit_amount_residual, -credit_amount_residual)
            has_debit_residual_left = not debit_line.company_currency_id.is_zero(debit_amount_residual) and debit_amount_residual > 0.0
            has_credit_residual_left = not credit_line.company_currency_id.is_zero(credit_amount_residual) and credit_amount_residual < 0.0
            has_debit_residual_curr_left = not debit_line_currency.is_zero(debit_amount_residual_currency) and debit_amount_residual_currency > 0.0
            has_credit_residual_curr_left = not credit_line_currency.is_zero(credit_amount_residual_currency) and credit_amount_residual_currency < 0.0

            if debit_line_currency == credit_line_currency:
                # Reconcile on the same currency.
                return super()._prepare_reconciliation_partials()

            else:
                # Reconcile on the company's currency.

                # The debit line is now fully reconciled since amount_residual is 0.
                if not has_debit_residual_left:
                    debit_line = None
                    continue

                # The credit line is now fully reconciled since amount_residual is 0.
                if not has_credit_residual_left:
                    credit_line = None
                    continue
                ctx = self.env.context.copy()
                if debit_line.move_id.currency_flag and debit_line.move_id.exchange_rate > 0:
                    ctx.update(bill_rate= 1 / debit_line.move_id.exchange_rate)
                min_debit_amount_residual_currency = credit_line.with_context(ctx).company_currency_id._convert(
                    min_amount_residual,
                    debit_line.currency_id,
                    credit_line.company_id,
                    credit_line.date,
                )
                min_debit_amount_residual_currency = fix_remaining_cent(
                    debit_line.currency_id,
                    debit_amount_residual_currency,
                    min_debit_amount_residual_currency,
                )

                if credit_line.move_id.currency_flag and credit_line.move_id.exchange_rate > 0:
                    ctx.update(bill_rate= 1 / credit_line.move_id.exchange_rate)
                min_credit_amount_residual_currency = debit_line.with_context(ctx).company_currency_id._convert(
                    min_amount_residual,
                    credit_line.currency_id,
                    debit_line.company_id,
                    debit_line.date,
                )
                min_credit_amount_residual_currency = fix_remaining_cent(
                    credit_line.currency_id,
                    -credit_amount_residual_currency,
                    min_credit_amount_residual_currency,
                )

            debit_amount_residual -= min_amount_residual
            debit_amount_residual_currency -= min_debit_amount_residual_currency
            credit_amount_residual += min_amount_residual
            credit_amount_residual_currency += min_credit_amount_residual_currency

            partials_vals_list.append({
                'amount': min_amount_residual,
                'debit_amount_currency': min_debit_amount_residual_currency,
                'credit_amount_currency': min_credit_amount_residual_currency,
                'debit_move_id': debit_line.id,
                'credit_move_id': credit_line.id,
            })

        return partials_vals_list


    def _create_exchange_difference_move(self):
        res = super(AccountMoveLine, self)._create_exchange_difference_move()
        if res != None:
            ref = self[0].move_id.name + ' ' + (self[0].move_id.ref or '')
            res.ref = ref
        return res