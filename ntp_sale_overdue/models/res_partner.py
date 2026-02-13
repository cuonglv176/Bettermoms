# __author__ = 'BinhTT'

from odoo import fields, api, models
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from bokeh.plotting import figure, show
from bokeh.embed import components
import json
from bokeh.models import DatetimeTickFormatter

class NTPResPartnerOVerdue(models.Model):
    _inherit = 'res.partner'
    late_amount_due = fields.Float('Late Amount Due', compute_sudo=True, compute='compute_late_amount_due')
    max_overdue_day = fields.Integer('Max Overdue Days', compute='compute_late_amount_due')
    saleoverdue_summary = fields.Text(compute='compute_late_amount_due')
    bokeh_chart = fields.Text(
        string='Bokeh Chart',
        compute='_compute_bokeh_chart',
    )
    period = fields.Selection([('6', '6 Months'), ('12', '12 Months')], 'Period', default='6')
    payment_summary = fields.Text(
        string='Payment Summary',
        compute='_compute_payment_summary',
    )

    @api.depends('period')
    def _compute_payment_summary(self):
        self.payment_summary = ''
        payment_summary = {'count_so': {'string': 'Count of Sale Order', 'data': {}},
                           'sum_so': {'string': 'Sum of Sale Order', 'data': {}},
                           'ar_so': {'string': 'Current AR', 'data': {}},
                           'payment_so': {'string': 'Payment', 'data': {}}}
        header = []
        for range_month in range(0, int(self.period)):
            first_day = date.today() + relativedelta(months=-range_month, day=1)
            last_day = date.today() + relativedelta(months=-range_month + 1, days=-1, day=1)
            header += [first_day.strftime('%b')]
            payment_summary.get('count_so').get('data').update({first_day.strftime('%b'): 0})
            payment_summary.get('sum_so').get('data').update({first_day.strftime('%b'): 0})
            payment_summary.get('ar_so').get('data').update({first_day.strftime('%b'): 0})
            payment_summary.get('payment_so').get('data').update({first_day.strftime('%b'): 0})
            if self.ids:
                sale_objs = self.env['sale.order'].search([['state', 'in', ['sale', 'done']], ['partner_id', 'child_of', self.ids],
                                                           ['date_order', '<=', last_day], ['date_order', '>=', first_day]])
                payment_summary.get('count_so').get('data').update({first_day.strftime('%b'): len(sale_objs)})

                total = 0
                amount_residual = 0
                payment = []
                for sale in sale_objs:
                    total += sale.amount_total
                    if not sale.invoice_ids.filtered(lambda x: x.state == 'posted'):
                        amount_residual += sale.amount_total
                    for invoice in sale.invoice_ids.filtered(lambda x: x.state == 'posted'):
                        amount_residual += invoice.amount_residual
                        payment += invoice._get_reconciled_info_JSON_values()
                for p in payment:
                    old_payment = payment_summary.get('payment_so').get('data').get(p.get('date').strftime('%b')) or 0
                    payment_summary.get('payment_so').get('data').update({p.get('date').strftime('%b'): old_payment + p.get('amount')})

                payment_summary.get('sum_so').get('data').update({first_day.strftime('%b'): total})
                payment_summary.get('ar_so').get('data').update({first_day.strftime('%b'): amount_residual})
        self.payment_summary = self.build_payment_summary_result(payment_summary, header)

    def build_payment_summary_result(self, data_list: dict, header):
        template = """
            <style>
                .styled-table {
                    border-collapse: collapse;
                    // margin: 25px 0;
                    font-family: sans-serif;
                    min-width: 400px;
                    width: 100%;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
                }
                .styled-table thead tr {
                    background-color: #714B67;
                    color: #f6f7fa;
                    text-align: left;
                }
                .styled-table th, .styled-table td {
                    padding: 3px 10px;
                }
                .styled-table tbody tr {
                    border-bottom: 1px solid #dddddd;
                }

                .styled-table tbody tr:nth-of-type(even) {
                    background-color: #f3f3f3;
                }

                .styled-table tbody tr:last-of-type {
                    border-bottom: 2px solid #714B67;
                    background-color: #714B67;
                    color: #f6f7fa;
                }

                .styled-table tbody tr.to_reconcile {
                    color: red;
                }
            </style>

            <table class="styled-table">
            <thead>
                <tr>
                <th/>
                    """
        for header_data in header:
            template += f""" <th>{header_data}</th>"""
        template += """
                </tr>
            </thead>
            <tbody>
        """
        total = 0
        for key, item_data in data_list.items():
            data = f"""
            <tr class="">
                <td>{item_data['string']}</td>"""
            for header_data in header:
                data += f""" <td>{"{:0,.0f}".format(item_data.get('data').get(header_data))}</th>"""
            data += """</tr>"""
            data = data.strip()
            template += data
        template += "</tbody></table>"
        return template
    def _compute_bokeh_chart(self):
        self.bokeh_chart = json.dumps({"div": '', "script": ''})
        if self.id:
            calculate_date = self.env['ir.config_parameter'].sudo().get_param('sale_overdue.date', 'effective_date')
            sale_objs = self.env['sale.order'].search([['state', 'in', ['sale', 'done']], ['partner_id', 'child_of', self.id]])
            x_value = []
            y_value = []
            x = 1
            y = 0
            amount_total = 0
            payment_data = {}
            payment_info = []
            to_date = date.today().month
            from_date = date.today().month
            for rec in sale_objs:
                lasted_payment_date = False
                from_date = rec[calculate_date] or rec.date_order
                if type(from_date) is datetime:
                    from_date = from_date.date().month
                to_date = date.today().month
                for invoice in rec.invoice_ids.sorted():
                    payment_info += invoice._get_reconciled_info_JSON_values()
                amount_total += rec.amount_total
            for payment in sorted(payment_info, key=lambda d: d['date']):
                y = payment.get('amount', 0) / (amount_total or 1) * 100
                payment_data.update({payment.get('date').month:  payment_data.get(payment.get('date').month, 0) + y})
                if not lasted_payment_date or payment.get('date').month > lasted_payment_date:
                    lasted_payment_date = payment.get('date').month
                if payment.get('date').month < from_date:
                    from_date = payment.get('date').month
                to_date = lasted_payment_date or to_date
            y = 0
            for x_month in range(0, (to_date - from_date) + 1):
                next_date = from_date + x_month
                # x_value = x_value + [(date.today() + relativedelta(month=next_date)).strftime('%b')]
                x_value += [datetime.combine(date.today() + relativedelta(month=next_date, day=1), datetime.min.time())]
                y = payment_data.get(next_date, 0)
                y_value += [min(y, 100)]
                    # Design your bokeh figure:
                # Design your bokeh figure:
            p = figure(sizing_mode="stretch_width", tools="pan,wheel_zoom,box_zoom,reset",
                       y_axis_label='Payment Percentage',
                       x_axis_type="datetime",
                       y_range=(0, 100),
                       )  # import that as `from bokeh.plotting import figure`
            line = p.vbar(x=x_value, top=y_value, width=timedelta(days=30), bottom=0, color='blue',)
            # p.line([0, 2], [1, 8], line_width=5)
            p.xaxis[0].formatter = DatetimeTickFormatter(months="%b")
            # p.xaxis[0].formatter = NumeralTickFormatter(format='')
            p.y_range.start = 0
            # p.y_range.stop = 100
            script, div = components(p, wrap_script=False)
            self.bokeh_chart = json.dumps({"div": div, "script": script})



    def build_saleoverdue_summary_xml(self, saleoverdue_summary):
        template = """
        <div class="o_overdue_sale_container d-flex o_form_statusbar text-center"> """
        for item in saleoverdue_summary:
                template += """<div t-attf-class="o_overdue_card o_arrow_button flex-grow-1 d-flex flex-column border-right-0">
                    <div class="content_center">
                        <div>
                            <span t-esc='"""
                template += item.get('value')  +  """' class="h2 o_overdue_purple"/>"""
                template += """
                        </div>
                        <b class="m-2 " data-toggle="tooltip" t-att-title='"""
                template +=item.get('tooltip') + """'>"""

                template += """<span t-esc='""" + item.get('title') + """'/>"""
                template += """</b> </div></div>"""



        template += """</div>"""
        return template

        
    def compute_late_amount_due(self):
        for partner in self:

            partner.late_amount_due = 0
            partner.max_overdue_day = 0
            partner.saleoverdue_summary = 0
            if partner and partner.id:
                sale_objs = self.env['sale.order'].search([('partner_id', 'child_of', partner.id), ('remained_amount', '>', 0)])
                saleoverdue_summary = self.env['sale.order'].get_overdue_dashboard(['&', '&', ['state', 'in', ['sale', 'done']], ['effective_date', '!=', False], ['partner_id', 'child_of', partner.id]])
                partner.saleoverdue_summary = partner.build_saleoverdue_summary_xml(saleoverdue_summary)
                for sale in sale_objs:
                    partner.late_amount_due += sale.late_amount_due
                    partner.max_overdue_day = max(sale.overdue_days, partner.max_overdue_day)

    def get_sale_detail_late_amount(self):
        action = self.env.ref('ntp_sale_overdue.action_payment_management')
        action_data = action.read()[0]
        action_data.update(domain=[('partner_id', 'child_of', self.id), ('remained_amount', '>', 0)])
        return action_data