# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    @api.model
    def _get_dates_period(self, options, date_from, date_to, mode, period_type=None, strict_range=False):
        output = super(AccountReport, self)._get_dates_period(options, date_from, date_to, mode, period_type, strict_range)

        if output.get('period_type') == 'month':
            if self.env.user.lang == 'vi_VN':
                string = format_date(self.env, fields.Date.to_string(date_to), date_format='MM yyyy')
                output['string'] = 'Tháng ' + string

        return output


class ReportAccountAgedPartner(models.AbstractModel):
    _inherit = 'account.aged.partner'

    invoice_user_name = fields.Char(string="Seller")

    def build_sql(self):
        sql = """
            SELECT
                {move_line_fields},
                account_move_line.partner_id AS partner_id,
                partner.name AS partner_name,
                COALESCE(trust_property.value_text, 'normal') AS partner_trust,
                COALESCE(account_move_line.currency_id, journal.currency_id) AS report_currency_id,
                account_move_line.payment_id AS payment_id,
                COALESCE(account_move_line.date_maturity, account_move_line.date) AS report_date,
                account_move_line.expected_pay_date AS expected_pay_date,
                partner1.name AS invoice_user_name,
                move.move_type AS move_type,
                move.name AS move_name,
                journal.code AS journal_code,
                account.name AS account_name,
                account.code AS account_code,""" + ','.join([("""
                CASE WHEN period_table.period_index = {i}
                THEN %(sign)s * ROUND((
                    account_move_line.balance - COALESCE(SUM(part_debit.amount), 0) + COALESCE(SUM(part_credit.amount), 0)
                ) * currency_table.rate, currency_table.precision)
                ELSE 0 END AS period{i}""").format(i=i) for i in range(6)]) + """
            FROM account_move_line
            JOIN account_move move ON account_move_line.move_id = move.id
            JOIN res_users ON res_users.id = move.invoice_user_id
            JOIN res_partner partner1 ON partner1.id = res_users.partner_id
            JOIN account_journal journal ON journal.id = account_move_line.journal_id
            JOIN account_account account ON account.id = account_move_line.account_id
            JOIN res_partner partner ON partner.id = account_move_line.partner_id
            LEFT JOIN ir_property trust_property ON (
                trust_property.res_id = 'res.partner,'|| account_move_line.partner_id
                AND trust_property.name = 'trust'
                AND trust_property.company_id = account_move_line.company_id
            )
            JOIN {currency_table} ON currency_table.company_id = account_move_line.company_id
            LEFT JOIN LATERAL (
                SELECT part.amount, part.debit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(date)s
            ) part_debit ON part_debit.debit_move_id = account_move_line.id
            LEFT JOIN LATERAL (
                SELECT part.amount, part.credit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(date)s
            ) part_credit ON part_credit.credit_move_id = account_move_line.id
            JOIN {period_table} ON (
                period_table.date_start IS NULL
                OR COALESCE(account_move_line.date_maturity, account_move_line.date) <= DATE(period_table.date_start)
            )
            AND (
                period_table.date_stop IS NULL
                OR COALESCE(account_move_line.date_maturity, account_move_line.date) >= DATE(period_table.date_stop)
            )
            WHERE account.internal_type = %(account_type)s
            GROUP BY account_move_line.id, partner.id, partner1.name,trust_property.id, journal.id, move.id, account.id,
                     period_table.period_index, currency_table.rate, currency_table.precision
        """
        return sql

    @api.model
    def _get_sql(self):
        options = self.env.context['report_options']
        sql = self.build_sql()
        query = sql.format(
            move_line_fields=self._get_move_line_fields('account_move_line'),
            currency_table=self.env['res.currency']._get_query_currency_table(options),
            period_table=self._get_query_period_table(options),
        )
        params = {
            'account_type': options['filter_account_type'],
            'sign': 1 if options['filter_account_type'] == 'receivable' else -1,
            'date': options['date']['date_to'],
        }
        return self.env.cr.mogrify(query, params).decode(self.env.cr.connection.encoding)

    @api.model
    def _get_column_details(self, options):
        return [
            self._header_column(),
            self._field_column('partner_name'),
            self._field_column('invoice_user_name'),
            self._field_column('report_date'),
            self._field_column('journal_code', name="Journal"),
            self._field_column('account_name', name="Account"),
            self._field_column('expected_pay_date'),
            self._field_column('period0', name=_("As of: %s") % format_date(self.env, options['date']['date_to'])),
            self._field_column('period1', sortable=True),
            self._field_column('period2', sortable=True),
            self._field_column('period3', sortable=True),
            self._field_column('period4', sortable=True),
            self._field_column('period5', sortable=True),
            self._custom_column(  # Avoid doing twice the sub-select in the view
                name=_('Total'),
                classes=['number'],
                formatter=self.format_value,
                getter=(
                    lambda v: v['period0'] + v['period1'] + v['period2'] + v['period3'] + v['period4'] + v['period5']),
                sortable=True,
            ),
        ]


class ReportGenericTaxReport(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    def get_tax_data(self, start_date, end_date, move_type, state):

        # get tax 10 for GTGT nhà thầu nước ngoài
        tax = self.env['account.tax'].search([('company_id', '=', self.env.company.id), ('type_tax_use', '=', 'sale' if 'out_invoice' in move_type else 'purchase'), ('amount', '=', 10)])
        if len(tax.ids) > 0:
            tax_id = tax[0].id
        else:
            tax_id = 0

        sql = """SELECT 
                    Case
                        When account_move.move_type = 'entry' Then %(tax)s
                        Else account_tax.id End
                    AS tax_id,
                    account_move.vsi_series, account_move.vsi_number, account_move.invoice_date, 
                    Case
                        When account_move.move_type = 'in_invoice' OR account_move.move_type = 'in_refund' Then branch2.name
                        When account_move.move_type = 'out_invoice' OR account_move.move_type = 'out_refund' Then branch1.name
                        Else '' End
                    AS branch_name,
                    Case
                        When account_move.move_type = 'in_invoice' OR account_move.move_type = 'in_refund' Then 
                            CASE
                                WHEN res_partner.name IS NULL OR res_partner.name = '' THEN res_partner."name"
                                ELSE res_partner.name
                            END
                        When account_move.move_type = 'entry' Then account_move."buyerName" 
                        When account_move.move_type = 'out_invoice' OR account_move.move_type = 'out_refund' Then res_partner.name End
                    AS partner_name,
                    res_partner.vat, account_tax.name,
                    SUM (
                        CASE
                            WHEN account_move.move_type = 'entry' THEN (account_move_line.debit * 10)
                            WHEN account_move_line.tax_line_id IS Not Null THEN account_move_line.tax_base_amount
                            WHEN account_move_line.tax_line_id IS Null AND price_subtotal < 0 THEN - ABS(account_move_line.balance)
                            WHEN account_move_line.tax_line_id IS Null AND price_subtotal >= 0 THEN ABS(account_move_line.balance)
                            END 
                                ) As price_subtotal,
                    SUM (
                        CASE
                            WHEN account_move.move_type = 'entry' THEN account_move_line.debit
                            WHEN account_move_line.tax_line_id IS Not Null AND price_subtotal < 0 THEN - ABS(account_move_line.balance)
                            WHEN account_move_line.tax_line_id IS Not Null AND price_subtotal >= 0 THEN ABS(account_move_line.balance)
                            WHEN account_move_line.tax_line_id IS Null THEN 0
                            END 
                                ) as amount_tax,
                    account_move.vsi_template, account_move.invoice_date, account_move.move_type
                    FROM account_move_line 
                    Inner join account_move On account_move.id = account_move_line.move_id
                    Left join account_move_line_account_tax_rel on account_move_line.id = account_move_line_account_tax_rel.account_move_line_id
                    Left join account_tax On 
                    CASE
                        WHEN account_move.move_type = 'entry' THEN account_tax.id = %(tax)s
                        WHEN account_move_line.tax_line_id IS NOT NULL THEN account_tax.id = account_move_line.tax_line_id
                        ELSE account_tax.id = account_move_line_account_tax_rel.account_tax_id
                    END 
                    Left join res_partner On res_partner.id = account_move.partner_id
                    Left join company_branch branch1 On branch1.id = account_move.company_branch_id
                    Left join company_branch branch2 On branch2.id = account_move.company_branch_vat
                    Left join account_journal account_journal On account_journal.id = account_move_line.journal_id 
                    WHERE ((account_move.move_type = 'out_invoice' OR account_move.move_type = 'out_refund') OR (account_move.move_type = 'in_invoice' OR account_move.move_type = 'in_refund') OR (account_move.move_type = 'entry'))
                    AND account_move.state = '%(state)s'
                    -- 20211014 Epsilo yêu cầu bỏ hết hóa đơn có payment_state = reversed
                    -- 20211015 Epsilo yêu cầu bao gồm hết hóa đơn có payment_state = reversed
                    -- AND account_move.payment_state IS DISTINCT FROM 'reversed' 
                    AND (account_move.move_type in %(move_type)s )
                    AND account_move.company_id = '%(company_id)s'
                    And  
                        Case (select count(*) from account_move_line aml where aml.move_id = account_move_line.move_id and aml.tax_line_id IS Not Null)
                            When (0) Then (account_move_line.tax_line_id IS Null And account_move_line.exclude_from_invoice_tab = False)
                            ELSE (account_move_line.tax_line_id IS Not Null And account_move_line.exclude_from_invoice_tab = True ) 
                        END
                    GROUP BY account_tax.id, account_move.vsi_template, account_move.vsi_series, account_move.vsi_number, account_move_line.date, partner_name, branch_name, res_partner.vat, account_tax.name, account_move.einvoice_date, account_move."buyerName", account_move.move_type, account_move.invoice_date, account_move.name  
                    Having ((account_move.move_type = 'in_invoice' OR account_move.move_type = 'in_refund' OR account_move.move_type = 'entry') AND account_move_line.date >= '%(start_date)s' And account_move_line.date <= '%(end_date)s' ) 
                    OR ((account_move.move_type = 'out_invoice' OR account_move.move_type = 'out_refund')AND account_move.invoice_date >= '%(start_date)s' And account_move.invoice_date <= '%(end_date)s' )
                    Order by account_tax.id , account_move_line.date Asc
                    ;"""

        tz = pytz.timezone(self.env.user.tz) or pytz.timezone('Asia/Ho_Chi_Minh')

        start = (pytz.utc.localize(fields.Datetime.from_string(start_date)).astimezone(tz)).strftime('%Y-%m-%d %H:%M:%S')
        end = (pytz.utc.localize(fields.Datetime.from_string(end_date)).astimezone(tz)).strftime('%Y-%m-%d %H:%M:%S')

        # GTGT cho nhà thầu nước ngoài
        # if move_type == 'in_invoice':
        #     move_type = "'in_invoice' OR ( account_move.move_type = 'entry' AND account_journal.code = 'VATNN' AND account_move_line.debit > 0)"
        # else:
        #     move_type = "'" + move_type + "'"

        sql = sql % ({
                        'tax': tax_id,
                        'state': state,
                        'start_date': start,
                        'end_date': end,
                        'move_type': move_type,
                        'company_id': self.env.company.id
                      })
        self.env.cr.execute(sql)
        res = self.env.cr.fetchall()

        return res

    def create_sheet(self, workbook, sheet_name, date_from, date_to, move_type, state, sheet_title):
        header_style = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter',
             'bg_color': '#BE1622', 'font_color': 'white', 'border': 1})
        header_style_1 = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bold': True, 'valign': 'vcenter', 'border': 1,
             'bg_color': 'yellow'})
        title_style = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'bottom': 2, 'align': 'center'})

        title_style_footer = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True})
        title_style_footer_2 = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'align': 'center'})
        title_style_footer_3 = workbook.add_format(
            {'font_name': 'Times New Roman', 'align': 'center'})

        sheet_sale = workbook.add_worksheet(sheet_name)
        sheet_sale.set_column('A:A', 3)
        sheet_sale.set_column('B:B', 20)
        sheet_sale.set_column('C:C', 20)
        sheet_sale.set_column('D:D', 25)
        sheet_sale.set_column('K:K', 20)
        sheet_sale.set_column('L:L', 15)
        sheet_sale.set_column('F:F', 15)
        sheet_sale.set_column('I:I', 15)
        sheet_sale.set_column('J:J', 15)
        sheet_sale.set_column('H:H', 15)
        sheet_sale.set_column('E:E', 15)
        sheet_sale.merge_range(0, 0, 0, 10, sheet_title, title_style)
        sheet_sale.merge_range(1, 0, 1, 10, 'Từ ngày ' + date_from +' đến ngày ' + date_to, title_style)
        sheet_sale.merge_range(2, 0, 3, 0, 'STT', header_style)
        sheet_sale.write(4, 0, '(1)', title_style)
        sheet_sale.merge_range(2, 1, 2, 4, 'Hóa đơn, chứng từ ' + ('bán' if 'out_invoice' in move_type else 'mua'), header_style)
        sheet_sale.write(3, 1, 'Mẫu hóa đơn', header_style)
        sheet_sale.write(4, 1, '(2)', title_style)
        sheet_sale.write(3, 2, 'Ký hiệu hóa đơn', header_style)
        sheet_sale.write(4, 2, '(3)', title_style)
        sheet_sale.write(3, 3, 'Số hóa đơn', header_style)
        sheet_sale.write(4, 3, '(4)', title_style)
        sheet_sale.write(3, 4, 'Ngày, tháng, năm phát hành', header_style)
        sheet_sale.write(4, 4, '(5)', title_style)
        sheet_sale.write(4, 5, '(6)', title_style)
        sheet_sale.write(4, 6, '(7)', title_style)
        sheet_sale.write(4, 7, '(8)', title_style)
        sheet_sale.write(4, 8, '(9)', title_style)
        sheet_sale.write(4, 9, '(10)', title_style)
        sheet_sale.write(4, 10, '(11)', title_style)
        sheet_sale.merge_range(2, 5, 3, 5, 'Chi nhánh', header_style)
        sheet_sale.merge_range(2, 6, 3, 6, 'Tên người ' + ('mua' if 'out_invoice' in move_type else 'bán'), header_style)
        sheet_sale.merge_range(2, 7, 3, 7, 'Mã số thuế người ' + ('mua' if 'out_invoice' in move_type else 'bán'), header_style)
        sheet_sale.merge_range(2, 8, 3, 8, 'Doanh số ' + ('bán' if 'out_invoice' in move_type else 'mua') + ' chưa có thuế', header_style)
        sheet_sale.merge_range(2, 9, 3, 9, 'Thuế GTGT', header_style)
        sheet_sale.merge_range(2, 10, 3, 10, 'Ghi chú', header_style)
        sale_tax = self.get_tax_data(date_from, date_to, move_type, state)
        row = 5
        col = 0

        current_tax = -1
        stt = 0
        total_ammount_by_tax = 0
        total_tax_ammount_by_tax = 0
        total_ammount_all = 0
        total_tax_ammount_all = 0
        for tax in sale_tax:
            stt += 1
            if current_tax != tax[0]:
                # print sum each tax
                if current_tax != -1:
                    row += 1
                    sheet_sale.write(row, 1, 'Tổng từng phần', title_style)
                    sheet_sale.write(row, 8, total_ammount_by_tax, title_style)
                    sheet_sale.write(row, 9, total_tax_ammount_by_tax, title_style)
                row += 1
                tax_name_header = tax[7]
                if tax_name_header is None or tax_name_header == '':
                    # tax_name_header = 'Thuế GTGT được khấu trừ 0%'
                    tax_name_header = 'Không chịu thuế'

                sheet_sale.merge_range(row, 0, row, 10, tax_name_header, header_style_1)

                # reset value
                current_tax = tax[0]
                total_ammount_by_tax = 0
                total_tax_ammount_by_tax = 0

            total = (tax[8] or 0.0) if (tax[12] == 'out_invoice' or tax[12] == 'in_invoice') else (-tax[8] or 0.0)
            total_tax = (tax[9] or 0.0) if (tax[12] == 'out_invoice' or tax[12] == 'in_invoice') else (-tax[9] or 0.0)
            total_ammount_by_tax += total
            total_tax_ammount_by_tax += total_tax
            total_ammount_all += total
            total_tax_ammount_all += total_tax
            sheet_sale.write(row + 1, 0, stt, title_style)
            sheet_sale.write(row + 1, 1, tax[10], title_style)
            sheet_sale.write(row + 1, 2, tax[1], title_style)
            sheet_sale.write(row + 1, 3, tax[2], title_style)
            invoice_date = tax[3] if 'in_invoice' in move_type else tax[11]
            sheet_sale.write(row + 1, 4, (invoice_date.strftime("%d/%m/%Y") if invoice_date is not None else ''), title_style)
            sheet_sale.write(row + 1, 5, tax[4], title_style)
            sheet_sale.write(row + 1, 6, tax[5], title_style)
            sheet_sale.write(row + 1, 7, tax[6], title_style)
            sheet_sale.write(row + 1, 8, total, title_style)
            sheet_sale.write(row + 1, 9, total_tax, title_style)
            sheet_sale.write(row + 1, 10, '', title_style)
            row += 1

        row += 1
        sheet_sale.write(row, 1, 'Tổng từng phần', title_style)
        sheet_sale.write(row, 8, total_ammount_by_tax, title_style)
        sheet_sale.write(row, 9, total_tax_ammount_by_tax, title_style)

        sheet_sale.write(row + 1, 0, "Tổng", title_style_footer)
        sheet_sale.write(row + 1, 8, total_ammount_all, title_style_footer)
        sheet_sale.write(row + 1, 9, total_tax_ammount_all, title_style_footer)
        # sheet_sale.merge_range(row + 2, 0, row + 2, 4, 'Tổng doanh thu hàng hóa dịch vụ bán ra', title_style_footer)
        # sheet_sale.merge_range(row + 3, 0, row + 3, 4, 'Tổng thuế GTGT của hàng hóa, dịch vụ bán ra',
        #                        title_style_footer)
        # sheet_sale.merge_range(row + 4, 0, row + 4, 4, 'Tổng doanh thu hàng hóa, dịch vụ bán ra chịu thuế GTGT',
        #                        title_style_footer)
        sheet_sale.merge_range(row + 6, 1, row + 6, 3, 'NHÂN VIÊN ĐẠI LÝ THUẾ', title_style_footer)
        sheet_sale.merge_range(row + 7, 1, row + 7, 3, 'Họ và tên', title_style_footer)
        sheet_sale.merge_range(row + 8, 1, row + 8, 3, 'Chứng chỉ hành nghê số', title_style_footer)
        sheet_sale.merge_range(row + 6, 5, row + 6, 9, 'Ngày ... tháng ... năm ...', title_style_footer_3)
        sheet_sale.merge_range(row + 7, 5, row + 7, 9, 'NGƯỜI NỘP THUẾ hoặc', title_style_footer_2)
        sheet_sale.merge_range(row + 8, 5, row + 8, 9, 'ĐẠI DIỆN HỢP PHÁP CỦA NGƯỜI NỘP THUẾ', title_style_footer_2)
        sheet_sale.merge_range(row + 9, 5, row + 9, 9, 'ký, ghi rõ họ tên, chức vụ và đóng dấu (nếu có)',
                               title_style_footer_3)

    def get_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ctx = self._set_context(options)
        ctx.update({'no_format': True, 'print_mode': True, 'prefetch_fields': False})
        self.create_sheet(workbook, 'BK mua vào', ctx['date_from'], ctx['date_to'], tuple(['in_invoice', 'in_refund']), 'posted', 'BẢNG KÊ HÓA ĐƠN, CHỨNG TỪ HÀNG HÓA, DỊCH VỤ MUA VÀO')
        self.create_sheet(workbook, 'BK bán ra', ctx['date_from'], ctx['date_to'], tuple(['out_invoice', 'out_refund']), 'posted', 'BẢNG KÊ HÓA ĐƠN, CHỨNG TỪ HÀNG HÓA, DỊCH VỤ BÁN RA')
        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file

    def _get_total_line_eval_dict(self, period_balances_by_code, period_date_from, period_date_to, options):
        """ Overridden in order to add the net profit of the period to the variables
        available for the computation of total lines in GST Return F5 report.
        """
        eval_dict = super(ReportGenericTaxReport, self)._get_total_line_eval_dict(period_balances_by_code, period_date_from, period_date_to, options)

        if self.env.company.country_id.code == 'SG':
            gross_revenue_query = """select sum(aml.credit) - sum(aml.debit)
                                  from account_move_line aml
                                  join account_account account
                                  on account.id = aml.account_id
                                  join account_account parent_account
                                  on parent_account.id = account.parent_id
                                  join account_move move
                                  on move.id = aml.move_id
                                  where
                                  parent_account.code = '411'
                                  and move.state = 'posted'
                                  and aml.date <= %(date_to)s
                                  and aml.date >= %(date_from)s
                                  and move.company_id = %(company_id)s;"""

            params = {
                'date_to': period_date_to,
                'date_from': period_date_from,
                'company_id': self.env.company.id,
            }
            self.env.cr.execute(gross_revenue_query, params)

            gross_revenue = self.env.cr.fetchall()[0][0]

            promotion_query = """select sum(aml.debit) - sum(aml.credit)
                                              from account_move_line aml
                                              join account_account account
                                              on account.id = aml.account_id
                                              join account_account parent_account
                                              on parent_account.id = account.parent_id
                                              join account_move move
                                              on move.id = aml.move_id
                                              where
                                              parent_account.code = '421'
                                              and move.state = 'posted'
                                              and aml.date <= %(date_to)s
                                              and aml.date >= %(date_from)s
                                              and move.company_id = %(company_id)s;"""

            params = {
                'date_to': period_date_to,
                'date_from': period_date_from,
                'company_id': self.env.company.id,
            }
            self.env.cr.execute(promotion_query, params)

            promotion_of_sale = self.env.cr.fetchall()[0][0]

            eval_dict['net_profit'] = (gross_revenue if gross_revenue else 0) - (promotion_of_sale if promotion_of_sale else 0)

        return eval_dict

    # 20211014 Epsilo yêu cầu bỏ hết hóa đơn có payment_state = reversed
    # 20211015 Epsilo yêu cầu bao gồm hết hóa đơn có payment_state = reversed
    def tax_tag_template_open_aml_bak(self, options, params=None):
        active_id = int(str(params.get('id')).split('_')[0])
        tag_template = self.env['account.tax.report.line'].browse(active_id)
        domain = [
                ('tax_tag_ids', 'in', tag_template.tag_ids.ids),
                ('tax_exigible', '=', True),
                ('move_id.payment_state', '!=', 'reversed')

        ]

        return self.open_action(options, domain)

    # 20211014 Epsilo yêu cầu bỏ hết hóa đơn có payment_state = reversed
    # 20211015 Epsilo yêu cầu bao gồm hết hóa đơn có payment_state = reversed
    def _compute_from_amls_grids_bak(self, options, dict_to_fill, period_number):
        """ Fills dict_to_fill with the data needed to generate the report, when
        the report is set to group its line by tax grid.
        """
        tables, where_clause, where_params = self._query_get(options)
        sql = """SELECT account_tax_report_line_tags_rel.account_tax_report_line_id,
                        SUM(coalesce(account_move_line.balance, 0) * CASE WHEN acc_tag.tax_negate THEN -1 ELSE 1 END
                                                 * CASE WHEN account_move.tax_cash_basis_rec_id IS NULL AND account_journal.type = 'sale' THEN -1 ELSE 1 END
                                                 * CASE WHEN """ + self._get_grids_refund_sql_condition() + """ THEN -1 ELSE 1 END)
                        AS balance
                 FROM """ + tables + """
                 JOIN account_move
                 ON account_move_line.move_id = account_move.id
                 JOIN account_account_tag_account_move_line_rel aml_tag
                 ON aml_tag.account_move_line_id = account_move_line.id
                 JOIN account_journal
                 ON account_move.journal_id = account_journal.id
                 JOIN account_account_tag acc_tag
                 ON aml_tag.account_account_tag_id = acc_tag.id
                 JOIN account_tax_report_line_tags_rel
                 ON acc_tag.id = account_tax_report_line_tags_rel.account_account_tag_id
                 JOIN account_tax_report_line report_line
                 ON account_tax_report_line_tags_rel.account_tax_report_line_id = report_line.id
                 WHERE """ + where_clause + """
                 AND report_line.report_id = %s
                 AND account_move_line.tax_exigible
                 AND account_journal.id = account_move_line.journal_id
                 -- 20211014 Epsilo yêu cầu bỏ hết hóa đơn có payment_state = reversed
                 -- 20211015 Epsilo yêu cầu bao gồm hết hóa đơn có payment_state = reversed
                 -- AND account_move.payment_state != 'reversed'
                 GROUP BY account_tax_report_line_tags_rel.account_tax_report_line_id
        """

        params = where_params + [options['tax_report']]
        self.env.cr.execute(sql, params)

        results = self.env.cr.fetchall()
        for result in results:
            if result[0] in dict_to_fill:
                dict_to_fill[result[0]]['periods'][period_number]['balance'] = result[1]
                dict_to_fill[result[0]]['show'] = True