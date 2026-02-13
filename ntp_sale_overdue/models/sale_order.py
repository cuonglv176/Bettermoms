# __author__ = 'BinhTT'
import datetime
from odoo import models, api, fields, _
from datetime import datetime, date, timedelta
from statistics import median
from bokeh.plotting import figure, show
from bokeh.embed import components
from dateutil.relativedelta import relativedelta
import json
from bokeh.models import DatetimeTickFormatter


class NTPSaleOrder(models.Model):
    _inherit = 'sale.order'

    overdue_payment = fields.Char('OverDue Payment')
    due_date = fields.Date('Due Date', compute='_get_due_date', compute_sudo=True, store=True)
    compute_due_date = fields.Date('Compute Due Date', compute='_get_due_date', compute_sudo=True)
    expected_payments_days = fields.Float('Expected Payments Days', compute='_get_due_date', store=True, compute_sudo=True)
    payment_status = fields.Char('Payment Status')
    avg_payment_days = fields.Float('Avg Payment Days', compute='_avg_payments_days', store=True, compute_sudo=True)
    payment_percent = fields.Float('Payment %', compute='_avg_payments_days', store=True, compute_sudo=True)
    remained_amount = fields.Float('Amount Due',compute='_avg_payments_days', store=True, compute_sudo=True)
    overdue_status = fields.Char('Overdue Status', compute='_avg_payments_days', store=True, compute_sudo=True)
    overdue_days = fields.Integer(compute='_avg_payments_days', store=True, compute_sudo=True)
    overdue_status = fields.Char('Overdue Status', compute='_avg_payments_days', compute_sudo=True)
    target_payment_date = fields.Date('Target Payment Date')
    number_of_changing_target_payment_date = fields.Float('Number of Changing Target Payment Date', store=True, compute_sudo=True)
    number_payment = fields.Integer('Number of Payment', compute='_avg_payments_days', store=True, compute_sudo=True)
    amount_due_percent = fields.Float('Amount Due %', compute='_avg_payments_days', store=True, compute_sudo=True)
    payment_term_days = fields.Integer('Payment Term Days', compute='_avg_payments_days', store=True, compute_sudo=True)
    financing_status = fields.Integer('Financing Cost', compute='_avg_payments_days')
    paid_amount = fields.Float('Paid Amount', compute_sudo=True, compute='_avg_payments_days', store=True,)
    indue_paid_amount = fields.Float('In-due Paid Amount', store=True, compute_sudo=True, compute='_avg_payments_days')
    overdue_paid_amount = fields.Float('Over-due Paid Amount', store=True, compute_sudo=True, compute='_avg_payments_days')
    late_amount_due = fields.Float('Late Amount Due', store=True, compute_sudo=True, compute='_avg_payments_days')
    remaining_payment_days = fields.Integer('Remaining Payment Days', compute_sudo=True, compute='compute_remaining_payment_days',
                                            help='Remain of Payment Days from Today to payment Date')
    ignore_order = fields.Boolean('Ignore Over-due')
    ignore_manual_reason = fields.Many2one('ignore.manual', tracking=True)
    scheduled_date = fields.Date('Scheduled Date', compute='get_schedule_date')
    invoice_date = fields.Date('Invoice Date', compute='get_invoice_date')
    payment_status_ids = fields.One2many('sale.payment.status', 'order_id', compute='get_payment_status')
    bokeh_chart = fields.Text(
        string='Bokeh Chart',
        compute='_compute_bokeh_chart',
    )

    def get_payment_status(self):
        def get_invoice_json(invoice):
            data = []
            for debit_invoice in invoice.line_ids.filtered(lambda line: line.account_internal_type in ('receivable', 'payable')):
                data += [{'date': debit_invoice.date_maturity, 'invoice': True, 'amount': debit_invoice.balance, 'today': False}]
            return data
        for obj in self:
            obj.payment_status_ids = [(5, 0, 0)]
            payment_info = []
            for invoice in obj.invoice_ids.sorted():
                payment_info += get_invoice_json(invoice)
                payment_info += invoice._get_reconciled_info_JSON_values()
            amount_due_balance = 0
            payment_info += [{
                'date': date.today(),
                'late_due': 0,
                'amount_due': 0,
                'amount': 0,
                'amount_due_balance': 0,
                'paid_amount': 0,
                'order_id': obj.id,
                'today': True
            }]
            for aged in sorted(payment_info, key=lambda d: d['date']):
                payment_status_detail = {
                    'date': aged.get('date'),
                    'late_due':  0,
                    'amount_due': aged.get('amount') if aged.get('invoice', False) and not aged.get('today', False)else 0,
                    'amount_due_balance': amount_due_balance ,
                    'paid_amount': aged.get('amount') if not aged.get('invoice', False) and not aged.get('today', False) else 0,
                    'order_id': obj.id,
                    'today': aged.get('today', False),
                }
                amount_due_balance += (aged.get('amount') if aged.get('invoice', False) else -aged.get('amount')) if len(payment_info) > 1 else obj.amount_total
                payment_status_detail.update(amount_due_balance=amount_due_balance,
                                             late_due=amount_due_balance if obj.due_date and aged.get('date') > obj.due_date else 0)
                obj.payment_status_ids.create(payment_status_detail)
                # obj.payment_status_ids = [(0, 0, payment_status_detail)]

    def _compute_bokeh_chart(self):
        calculate_date = self.get_overdue_date_config()
        for rec in self:
            x_value = []
            y_value = []
            x = 1
            y = 0
            lasted_payment_date = False
            from_date = rec[calculate_date] or rec.date_order
            if type(from_date) is datetime:
                from_date = from_date.date()
            to_date = date.today()
            payment_data = {}
            payment_info = []
            for invoice in rec.invoice_ids.sorted():
                payment_info += invoice._get_reconciled_info_JSON_values()
            for payment in sorted(payment_info, key=lambda d: d['date']):
                y += payment.get('amount', 0) / (rec.amount_total or 1) * 100
                payment_data.update({payment.get('date'):  y})
                if not lasted_payment_date or payment.get('date') > lasted_payment_date:
                    lasted_payment_date = payment.get('date')
                if payment.get('date') < from_date:
                    from_date = payment.get('date')
            if round(rec.payment_percent) == 100:
                to_date = lasted_payment_date or to_date
            y = 0
            for x_day in range(0, (to_date - from_date).days + 1):
                next_date = from_date + relativedelta(days=x_day)
                x_value += [datetime.combine(next_date, datetime.min.time())]
                y = max(y, payment_data.get(next_date, 0))
                y_value += [min(y, 100)]
                # Design your bokeh figure:
            # p = figure()  # import that as `from bokeh.plotting import figure`
            # line = p.line([0, 2], [1, 8], line_width=5)
            # # (...)
            # # fill the record field with both markup and the script of a chart.
            # script, div = components(p, wrap_script=False)
            # rec.bokeh_chart = json.dumps({"div": div, "script": script})
            # Design your bokeh figure:
            p = figure(sizing_mode="stretch_width", tools="pan,wheel_zoom,box_zoom,reset",
                       y_axis_label='Payment Percentage',
                       x_axis_type="datetime",
                       y_range=(0, 100),
                       )  # import that as `from bokeh.plotting import figure`
            # # p.xaxis.formatter = DatetimeTickFormatter(days=['%d %B'], months=['%d %B'])
            line = p.vbar(x=x_value, top=y_value, width=timedelta(days=1), bottom=0, color='blue',)
            # p.line([0, 2], [1, 8], line_width=5)
            p.xaxis[0].formatter = DatetimeTickFormatter(days="%d %B %Y")
            # p.yaxis[0].formatter = NumeralTickFormatter(format='%')
            p.y_range.start = 0
            # p.y_range.stop = 100
            script, div = components(p, wrap_script=False)
            rec.bokeh_chart = json.dumps({"div": div, "script": script})

    def get_invoice_date(self):
        for r in self:
            r.invoice_date = False
            if r.invoice_ids:
                r.invoice_date = r.invoice_ids[0].invoice_date

    def get_schedule_date(self):
        for r in self:
            r.scheduled_date = False
            if r.picking_ids:
                r.scheduled_date = r.picking_ids[0].scheduled_date

    def ignore_manual(self):
        # self.write({'ignore_order': True})
        return {'type': 'ir.actions.act_window',
                'name': _('Ignore Manual Reason'),
                'res_model': 'ignore.manual.wizard',
                'target': 'new',
                'view_mode': 'form',
                # 'context': ctx,
                # 'views': [[view_id, 'form']],
                }

    def write(self, vals):
        if vals.get('target_payment_date'):
            target_payment = vals.get('target_payment_date')
            if type(vals.get('target_payment_date')) is str:
                target_payment = datetime.strptime(vals.get('target_payment_date'), '%Y-%m-%d').date()
            vals.update(number_of_changing_target_payment_date=self.number_of_changing_target_payment_date + 1,
                        remaining_payment_days=(target_payment - date.today()).days)
        return super(NTPSaleOrder, self).write(vals)

    @api.depends('target_payment_date')
    def compute_remaining_payment_days(self):
        for r in self:
            r.remaining_payment_days = 0

            if r.target_payment_date and r.due_date and r.payment_percent < 100:
                r.remaining_payment_days = (max(r.target_payment_date, r.due_date) - date.today()).days


    @api.depends('picking_ids.date_done')
    def _compute_effective_date(self):
        res = super(NTPSaleOrder, self)._compute_effective_date()
        for order in self:
            if not order.target_payment_date:
                order.target_payment_date = order.due_date
        return res

    @api.onchange('payment_term_id')
    def _get_target_paymnet_date(self):
        calculate_date = self.get_overdue_date_config()

        if self.payment_term_id:
            target_payment_date = self.payment_term_id.compute(self.amount_total, self[calculate_date], self.currency_id)
            if target_payment_date:
                self.target_payment_date = target_payment_date[0][0]
                if type(target_payment_date[0][0]) is str:
                    self.target_payment_date = datetime.strptime(target_payment_date[0][0], '%Y-%m-%d').date() or self[calculate_date]

    def get_overdue_date_config(self):
        """
        Returns rooturl for a specific given record.

        By default, it return the ir.config.parameter of sale_overdue.date
        but it can be overidden by model.

        :return: the sale_overdue.date for this record to calculate overdue
        :rtype: string

        """
        return self.env['ir.config_parameter'].sudo().get_param('sale_overdue.date', 'effective_date')
    # def _compute_due_date(self):
    #     calculate_date = self.get_overdue_date_config()
    #     for r in self:
    #         from_date = r[calculate_date]
    #         if type(from_date) is datetime:
    #             from_date = from_date.date()
    #         r.compute_due_date = from_date
    #         if r.payment_term_id:
    #             due_date = r.payment_term_id.term_compute(r.amount_total, from_date, r)
    #             if due_date:
    #                 r.compute_due_date = due_date[-1:][0][0]
    #                 if type(due_date[-1:][0][0]) is str:
    #                     r.compute_due_date = datetime.strptime(due_date[-1:][0][0], '%Y-%m-%d').date() or from_date

    @api.depends('effective_date', 'payment_term_id', 'invoice_ids.amount_residual')
    def _get_due_date(self):
        calculate_date = self.get_overdue_date_config()
        for r in self:
            from_date = r[calculate_date]
            if type(from_date) is datetime:
                from_date = from_date.date()
            r.due_date = from_date
            r.compute_due_date = from_date
            r.expected_payments_days = 0
            if r.payment_term_id:
                due_date = r.payment_term_id.compute(r.amount_total, from_date, r.currency_id)
                if due_date:
                    r.due_date = due_date[-1:][0][0]
                    r.compute_due_date = due_date[-1:][0][0]
                    if type(due_date[-1:][0][0]) is str:
                        r.due_date = datetime.strptime(due_date[-1:][0][0], '%Y-%m-%d').date() or from_date
                        r.compute_due_date = datetime.strptime(due_date[-1:][0][0], '%Y-%m-%d').date() or from_date

                if from_date:
                    r.expected_payments_days = r.get_payment_days(r.compute_due_date, from_date)

    def get_overdue_payment_info(self):
        invoice_ids = self.invoice_ids
        invoice_info = {'payment_date': '', 'due_date': self.due_date.strftime('%d-%b-%Y') if self.due_date else '', 'no_late_payment': 0,
                        'overdue_amount': 0, 'amount_due': self.remained_amount}
        payment_date = False

        def compute_invoice_late_payment(date, amount, invoice_info):
            amount_late_payment = self.compute_late_payment(date, self.compute_due_date, amount)
            invoice_info.update(no_late_payment=(invoice_info.get('no_late_payment') + amount_late_payment))
            if amount_late_payment > 0:
                invoice_info.update(overdue_amount=invoice_info.get('overdue_amount') + amount)
        if self.due_date:
            for invoice in invoice_ids:
                compute_invoice_late_payment(date.today(), invoice.amount_residual, invoice_info)
                payment_info = invoice._get_reconciled_info_JSON_values()
                for payment in payment_info:
                    if not payment_date or payment.get('date') > payment_date:
                        payment_date = payment.get('date')
                    compute_invoice_late_payment(payment.get('date'), payment.get('amount'), invoice_info)
            invoice_info.update(payment_date=(payment_date or date.today()).strftime('%d-%b-%Y'), no_late_payment=round(invoice_info.get('no_late_payment')) )
        return invoice_info

    def get_payment_days(self, end_date, start_date):
        return (end_date - start_date).days

    def compute_late_payment(self, payment_date, start_date, paid_amount):

        payment_days = self.get_payment_days(payment_date, start_date)
        number_late_payment = payment_days * paid_amount / (self.amount_total or 1)

        return (number_late_payment)

    @api.depends('invoice_ids.amount_residual')
    def _avg_payments_days(self):
        calculate_date = self.get_overdue_date_config()
        for r in self:
            from_date = r[calculate_date]
            if type(from_date) is datetime:
                from_date = from_date.date()
            r.remained_amount = r.amount_total
            r.avg_payment_days = overdue_amount = 0
            r.overdue_days = r.payment_percent = 0
            r.overdue_status = ''
            r.number_payment = r.financing_status = 0
            r.amount_due_percent = r.late_amount_due = 0
            r.payment_term_days = r.paid_amount = 0
            r.overdue_paid_amount = r.indue_paid_amount = 0
            lasted_payment_date = False
            if from_date:
                for invoice in r.invoice_ids:
                    # todo: calculate amount_payment_days base on invoice paid

                    payment_info = invoice._get_reconciled_info_JSON_values()
                    for payment in payment_info:
                        amount_payment_days = (r.compute_late_payment(payment.get('date'), from_date, payment.get('amount')))
                        # todo: lasted_payment_date to calculate financing cost

                        if not lasted_payment_date or payment.get('date') > lasted_payment_date:
                            lasted_payment_date = payment.get('date')
                        if amount_payment_days > 0:
                            overdue_amount += payment.get('amount')
                        # todo: amount_late_payment to calculate amount in-due or over-due
                        amount_late_payment = r.compute_late_payment(payment.get('date'), r.compute_due_date or from_date, payment.get('amount'))
                        if amount_late_payment > 0:
                            r.overdue_paid_amount += payment.get('amount')
                        else:
                            r.indue_paid_amount += payment.get('amount')

                        r.remained_amount -= payment.get('amount')
                        r.avg_payment_days += amount_payment_days
                        r.payment_percent += payment.get('amount') / (r.amount_total or 1) * 100
                        r.number_payment += 1
                        r.amount_due_percent = r.remained_amount / (r.amount_total or 1) * 100

                interest_rate = self.env['interest.rate'].search([('date', '<=', from_date)], order='date desc', limit=1)
                # todo: calculate amount due until today
                amount_payment_days = int(r.compute_late_payment(date.today(), from_date, r.remained_amount))
                amount_late_payment = r.compute_late_payment(date.today(), r.compute_due_date or from_date, r.remained_amount)
                if amount_payment_days > 0:
                    overdue_amount += r.remained_amount
                if amount_late_payment > 0:
                    r.late_amount_due += r.remained_amount
                r.avg_payment_days += amount_payment_days
                r.payment_term_days = ((r.compute_due_date or from_date) - from_date).days
                if r.remained_amount > 0 and r.remained_amount == r.amount_total:
                    r.overdue_days = (date.today() - (r.compute_due_date or from_date)).days
                else:
                    r.overdue_days = (r.avg_payment_days - r.expected_payments_days)
                if r.overdue_days < 0:
                    r.overdue_days = 0
                r.overdue_status = str(round(r.overdue_days)) + ' day(s)'
                # else:
                #     r.overdue_status =  str(round(r.overdue_days)) + ' day(s)'
                r.avg_payment_days = round(r.avg_payment_days)
                r.paid_amount = r.amount_total - r.remained_amount
                # if ignore_order, pay 100% and not remained amount
                if r.ignore_order:
                    r.paid_amount = r.amount_total
                    r.remained_amount = 0
                    r.payment_percent = 100
                    r.late_amount_due = 0
                    r.overdue_days = (r.avg_payment_days - r.expected_payments_days) if (r.avg_payment_days - r.expected_payments_days) > 0 else 0
                if interest_rate and overdue_amount > 0:
                    if not lasted_payment_date:
                        lasted_payment_date = date.today()
                    r.financing_status = (interest_rate.rate / 100) * overdue_amount * ((lasted_payment_date - (r.due_date or from_date)).days / 365)
        return

    @api.model
    def get_overdue_dashboard(self, domain=[]):
        calculate_date = self.get_overdue_date_config()

        sale_obj = self.search([('state', 'in', ('sale', 'done')), ('effective_date', '!=', False)])
        all_sale_obj = self.search([('state', 'in', ('sale', 'done')), ('effective_date', '!=', False)])
        if domain:
            sale_obj = self.search(domain)
            all_sale_obj = self.search(domain)
        overdue_day = overdue_order = 0
        overdue_list = indue_list = ()
        indue_order = indue_day = 0
        total_amount_due = 0
        maximum_overdue = minimum_indue = late_amount_due = 0
        for r in sale_obj:
            if r.overdue_days > 0:
                overdue_order += 1
                overdue_day += r.overdue_days
                overdue_list += (r.overdue_days,)
                maximum_overdue = max(r.overdue_days, maximum_overdue)

            else:
                indue_order += 1
                indue_day += r.overdue_days
                indue_list += (r.overdue_days,)
                minimum_indue = min(r.overdue_days, minimum_indue)
            late_amount_due += r.late_amount_due
            total_amount_due += r.remained_amount

        avg_overdue_day = round(overdue_day / (overdue_order or 1), 2)
        avg_indue_day = round(indue_day / (indue_order or 1), 2)
        percent_overdue = round(overdue_order/ (len(all_sale_obj) or 1) * 100 , 2)
        percent_indue = round(indue_order / (len(all_sale_obj) or 1) * 100 , 2)
        avg_overdue_day = str(avg_overdue_day) + '/ ' + str(median(overdue_list) if overdue_list else 0)
        avg_indue_day = str(avg_indue_day) + '/ ' + str(median(indue_list) if indue_list else 0)
        return [
            {'title': _('Total Late Amount Due/Total Amount Due'),
             'tooltip': _('Total Not Paid Amount Over-due'), 'value': '{:20,.0f}'.format(late_amount_due) + '/' + '{:20,.0f}'.format(total_amount_due) },
            {'title': _('Average/Median Days Late'),
             'tooltip': _('Average/Median Days Late is calculated as sum (days late) / number of Late Order'), 'value': avg_overdue_day },
            {'title': _('Average/Median Days In-Due'),
             'tooltip': _('Average/Median Days In-due is calculated as sum (days) / number of In-du Order'), 'value': avg_indue_day},
            {'title': _('Percentage Days Late/In-Due'),
             'tooltip': _('Percentage Late Order is calculated as Number of Late Order / All Order'), 'value': str(percent_overdue) + '%' + '/' + str(percent_indue) +'%'},
            # {'title': _('Percentage Days In-due'),
            #  'tooltip': _('Percentage In-Due Order is calculated as Number of In-Due Order / All Order'), 'value': str(percent_indue) + '%'},
            {'title': _('Maximum Days Late/In-Due'),
             'tooltip': _('Maximum Days late is calculated as Maximum Number of Days late'), 'value': str(maximum_overdue) + '/' +  str(minimum_indue) },

        ]