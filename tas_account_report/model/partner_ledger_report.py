# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz
from datetime import datetime, timedelta
import logging
import json
_logger = logging.getLogger(__name__)


class ReportPartnerLedger(models.AbstractModel):
    _inherit = "account.partner.ledger"

    filter_account_type = [
        {'id': 'receivable', 'name': _lt('Receivable'), 'selected': True},
        {'id': 'payable', 'name': _lt('Payable'), 'selected': False},
        {'id': 'other_receivable', 'name': _lt('Other Receivable - 13880001'), 'selected': False},
        {'id': 'other_payable', 'name': _lt('Other Payable - 33880001'), 'selected': False},
        {'id': 'advance_payment', 'name': _lt('Tạm ứng nhân viên - 14110001'), 'selected': False},
    ]

    def _get_reports_buttons(self, options):
        res = super(ReportPartnerLedger, self)._get_reports_buttons(options)
        res.append({'name': _('Xuất chi tiết công nợ'), 'action': 'export_detail_action', 'sequence': 8, 'file_export_type': _('XLSX')})
        return res

    def export_detail_action(self, options):
        options['report_name'] = 'detail_report'
        options['unfold_all'] = True
        return {
                'type': 'ir_actions_account_report_download',
                'data': {'model': self.env.context.get('model'),
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'financial_id': self.env.context.get('id'),
                         }
                }

    def generate_option_account_type(self, options):
        domain = []
        have_or = False

        for account_type_option in options.get('account_type', []):
            if account_type_option['selected']:
                if account_type_option['id'] == 'other_receivable':
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('account_id.code', '=', '13880001'))
                    have_or = True
                elif account_type_option['id'] == 'other_payable':
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('account_id.code', '=', '33880001'))
                    have_or = True
                elif account_type_option['id'] == 'advance_payment':
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('account_id.code', '=', '14110001'))
                    have_or = True
                else:
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('account_id.internal_type', '=', account_type_option['id']))
                    have_or = True
        return domain

    @api.model
    def _get_options_domain(self, options):
        domain = super(ReportPartnerLedger, self)._get_options_domain(options)

        for d in domain:
            if d[0] == 'account_id.internal_type':
                domain.remove(d)

        new_domain = domain + self.generate_option_account_type(options)

        return new_domain

    @api.model
    def _get_query_amls(self, options, expanded_partner=None, offset=None, limit=None):
        ''' Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:             The report options.
        :param expanded_partner:    The res.partner record corresponding to the expanded line.
        :param offset:              The offset of the query (used by the load more).
        :param limit:               The limit of the query (used by the load more).
        :return:                    (query, params)
        '''
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        # Get sums for the account move lines.
        # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
        if expanded_partner is not None:
            domain = [('partner_id', '=', expanded_partner.id)]
        elif unfold_all:
            domain = []
        elif options['unfolded_lines']:
            domain = [('partner_id', 'in', [int(line[8:]) for line in options['unfolded_lines']])]

        new_options = self._get_options_sum_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        ct_query = self.env['res.currency']._get_query_currency_table(options)

        query = '''
                SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name,
                    account_move_line.ref,
                    account_move_line.company_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    account_move_line.partner_id,
                    account_move_line.currency_id,
                    account_move_line.amount_currency,
                    account_move_line.matching_number,
                    ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                    ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                    ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                    account_move_line__move_id.name         AS move_name,
                    company.currency_id                     AS company_currency_id,
                    partner.name                            AS partner_name,
                    account_move_line__move_id.move_type    AS move_type,
                    account.code                            AS account_code,
                    account.name                            AS account_name,
                    journal.code                            AS journal_code,
                    journal.name                            AS journal_name,
                    account_move_line.einvoice_number       AS einvoice_number,
                    account_move_line.einvoice_date         AS einvoice_date,
                    account_move_line__move_id.vsi_series   AS vs_series,
                    account_move_line.countered_accounts    AS countered_accounts
                FROM account_move_line
                LEFT JOIN account_move account_move_line__move_id ON account_move_line__move_id.id = account_move_line.move_id
                LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                WHERE %s
                ORDER BY account_move_line.date, account_move_line.id
            ''' % (ct_query, where_clause)

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params

    @api.model
    def _get_report_line_move_line(self, options, partner, aml, cumulated_init_balance, cumulated_balance):
        line = super(ReportPartnerLedger, self)._get_report_line_move_line(options, partner, aml, cumulated_init_balance, cumulated_balance)
        if self._context.get('print_excel_mode'):
            e_invoice_date = aml['einvoice_date'] and format_date(self.env,
                                                                 fields.Date.from_string(aml['einvoice_date']))

            columns = [
                {'name': aml['move_name']},
                {'name': aml['einvoice_number']},
                {'name': aml['vs_series']},
                {'name': e_invoice_date or '', 'class': 'date'},
                {'name': aml['name']},
                {'name': aml['countered_accounts']},
                {'name': self.format_value(aml['debit'], blank_if_zero=True), 'class': 'number'},
                {'name': self.format_value(aml['credit'], blank_if_zero=True), 'class': 'number'},
                {'name': self.format_value(cumulated_balance), 'class': 'number'},
            ]
            line['columns'] = columns
        return line

    def get_excel_table(self, options):
        ctx = {'no_format': True, 'print_excel_mode': True, 'prefetch_fields': False}
        headers, lines = self.with_context(ctx)._get_table(options)
        headers = [[
                {'name': _('Ngày'), 'class': 'date'},
                {'name': _('Chứng từ')},
                {'name': _('Số HĐ')},
                {'name': _('Số Series')},
                {'name': _('Ngày HĐ'), 'class': 'date'},
                {'name': _('Diễn giải')},
                {'name': _('Tk đối ứng'), 'class': 'number'},
                {'name': _('Nợ'), 'class': 'number'},
                {'name': _('Có'), 'class': 'number'},
                {'name': _('Dư'), 'class': 'number'}]]

        return headers, lines

    def get_search_account(self, options):
        domain = []
        have_or = False

        for account_type_option in options.get('account_type', []):
            if account_type_option['selected']:
                if account_type_option['id'] == 'other_receivable':
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('code', '=', '13880001'))
                    have_or = True
                elif account_type_option['id'] == 'other_payable':
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('code', '=', '33880001'))
                    have_or = True
                elif account_type_option['id'] == 'advance_payment':
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('code', '=', '14110001'))
                    have_or = True
                else:
                    if have_or:
                        domain.insert(0, '|')
                    domain.append(('internal_type', '=', account_type_option['id']))
                    have_or = True
        domain

        accounts = self.env['account.account'].search(domain)
        output = ''
        separate = ''
        for account in accounts:
            output += separate + account.code
            separate = ', '

        cach_tinh_balance = 'receivable'

        if len(accounts) > 0 and (accounts[0].internal_type == 'payable' or accounts[0].code == '33880001'):
            cach_tinh_balance = 'payable'
        return output, cach_tinh_balance

    def get_xlsx(self, options, response=None):
        if 'report_name' in options:
            if options.get('report_name') == 'detail_report':
                return self.export_detail(options, response)
        return super(ReportPartnerLedger, self).get_xlsx(options, response)

    def export_detail(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        date_default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd', 'border': 1})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd', 'border': 1})
        default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#666666'})
        default_style_bold = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': 0})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'border': 1, 'font_size': 10, 'font_color':'blue'})
        level_0_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'bottom': 6, 'font_color': '#666666'})
        level_1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#666666', 'indent': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#666666'})
        level_2_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10,'border':1})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'border': 1, 'align': 'right'})
        report_name_style = workbook.add_format({'font_name': 'Arial','font_size': 14, 'bold': True, 'font_color': 'red', 'align': 'center', 'valign': 'vcenter'})
        title_style_center = workbook.add_format({'font_name': 'Arial','font_size': 10, 'bold': 0, 'align': 'center', 'valign': 'vcenter'})
        title_style_center_border = workbook.add_format({'border':1, 'font_name': 'Arial', 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color':'#DDEBF7'})
        number_title_bold_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'border': 1, 'align': 'right','font_size':10,'font_color':'blue'})
        border_format = workbook.add_format({'border': 1})

        # get data
        headers, lines = self.get_excel_table(options)
        accounts, cach_tinh_balance = self.get_search_account(options)

        # print company name
        y_offset = 0
        x_offset = 0
        sheet.set_column(0, 9, 8)
        sheet.set_column(1, 1, 16)
        sheet.set_column(5, 5, 30)
        sheet.set_column(7, 9, 12)
        sheet.fit_to_pages(1, 0)

        sheet.write(y_offset, x_offset, self.env.company.display_name, default_style_bold)
        y_offset += 1
        sheet.write(y_offset, x_offset, self.env.company.street, default_style_bold)
        # end print company name

        # print partner ledger
        cong_phat_sinh_no = 0
        cong_phat_sinh_co = 0
        cong_phat_sinh_balance = 0
        cuoi_ki_no = 0
        cuoi_ki_co = 0
        cuoi_ki_balance = 0
        first_partner = 0
        du_tren = 0

        date_from_string = datetime.strptime(options.get('date').get('date_from'), '%Y-%m-%d').strftime('%d/%m/%Y')
        date_to_string = datetime.strptime(options.get('date').get('date_to'), '%Y-%m-%d').strftime('%d/%m/%Y')

        for y in range(0, len(lines)):
            level = lines[y].get('level')
            if not lines[y].get('caret_options') and 'partner_id' in lines[y] and ((len(options['partner_ids']) and lines[y]['partner_id'] in options['partner_ids']) or len(options['partner_ids'])  == 0):
                # print cuoi ki
                if first_partner > 0:
                    sheet.conditional_format('A%d:J%d' % (y_offset,y_offset+2),{'type':'blanks', 'format': border_format})
                    sheet.write(y_offset, 5, "Cộng phát sinh", title_style)
                    sheet.write(y_offset, 7, "{:,}".format(round(cong_phat_sinh_no)), number_title_bold_style)
                    sheet.write(y_offset, 8, "{:,}".format(round(cong_phat_sinh_co)), number_title_bold_style)
                    sheet.write(y_offset, 9, "{:,}".format(round(cong_phat_sinh_balance)), number_title_bold_style)
                    y_offset += 1
                    sheet.write(y_offset, 5, "Số dư cuối kì", title_style)
                    sheet.write(y_offset, 7, "{:,}".format(round(cuoi_ki_no)), number_title_bold_style)
                    sheet.write(y_offset, 8, "{:,}".format(round(cuoi_ki_co)), number_title_bold_style)
                    sheet.write(y_offset, 9, "{:,}".format(round(abs(cuoi_ki_balance))), number_title_bold_style)
                # end print cuoi ki

                y_offset += 3
                merge_from = 'A'
                merge_to = 'J'
                sheet.merge_range(merge_from + str(y_offset)+':' + merge_to + str(y_offset), 'SỔ CHI TIẾT CÔNG NỢ', report_name_style)
                y_offset += 1
                sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset), 'Từ ngày ' + date_from_string + ' Đến ngày ' + date_to_string, title_style_center)
                y_offset += 1
                sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset), 'Tài khoản: ' + accounts, title_style_center)
                y_offset += 1
                sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset), 'Khách hàng: ' + lines[y].get('name'), title_style_center)
                y_offset += 1

                # print header
                for header in headers:
                    x_offset = 0
                    for column in header:
                        column_name_formated = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
                        colspan = column.get('colspan', 1)
                        if colspan == 1:
                            sheet.write(y_offset, x_offset, column_name_formated, title_style_center_border)
                        else:
                            sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1, column_name_formated,
                                              title_style_center_border)
                        x_offset += colspan
                # end print header
                y_offset += 1
                sheet.conditional_format('A%d:J%d' % (y_offset, y_offset + 1),{'type': 'blanks', 'format': border_format})
                sheet.write(y_offset, 5, "Số dư đầu kì", title_style)
                sheet.write(y_offset, 7, "0", number_title_bold_style)
                sheet.write(y_offset, 8, "0", number_title_bold_style)
                cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][0])
                du_tren = int(cell_value)
                sheet.write(y_offset, 9, "{:,}".format(du_tren), number_title_bold_style)

                cong_phat_sinh_no = lines[y]['columns'][1]['name']
                cong_phat_sinh_co = lines[y]['columns'][2]['name']
                cuoi_ki_balance = lines[y]['columns'][len(lines[y]['columns'])-1]['name']

                first_partner += 1
                y_offset += 1
            elif lines[y].get('caret_options'):
                style = level_3_style
                col1_style = level_3_col1_style

                # write the first column, with a specific style to manage the indentation
                cell_type, cell_value = self._get_cell_type_value(lines[y])
                if cell_type == 'date':
                    sheet.write_datetime(y_offset, 0, cell_value, date_default_col1_style)
                else:
                    sheet.write(y_offset, 0, cell_value, col1_style)

                # write all the remaining cells
                ps_no = 0
                ps_co = 0
                for x in range(1, len(lines[y]['columns']) + 1):
                    print(y_offset, x)
                    cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][x - 1])
                    if cell_type == 'date':
                        sheet.write_datetime(y_offset, x + lines[y].get('colspan', 1) - 1, cell_value,
                                             date_default_style)
                    else:
                        if (x-1) == len(lines[y]['columns'])-3:
                            ps_no = int(cell_value) if cell_value != '' else 0
                            sheet.write(y_offset, x + lines[y].get('colspan', 1) - 1, "{:,}".format(ps_no), style)
                        elif (x-1) == len(lines[y]['columns'])-2:
                            ps_co = int(cell_value) if cell_value != '' else 0
                            sheet.write(y_offset, x + lines[y].get('colspan', 1) - 1, "{:,}".format(ps_co), style)
                        elif (x-1) == len(lines[y]['columns'])-1:
                            if cach_tinh_balance == 'receivable':
                                du_tren = du_tren + (ps_no - ps_co)
                            elif cach_tinh_balance == 'payable':
                                du_tren = du_tren + (ps_co - ps_no)
                            sheet.write(y_offset, x + lines[y].get('colspan', 1) - 1, "{:,}".format(du_tren), style)
                        else:
                            sheet.write(y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, style)
                y_offset += 1
            # print each line here
        # print cuoi ki cho kh cuoi
        if first_partner > 0:
            sheet.conditional_format('A%d:J%d' % (y_offset, y_offset + 2), {'type': 'blanks', 'format': border_format})
            sheet.write(y_offset, 5, "Cộng phát sinh", title_style)
            sheet.write(y_offset, 7, "{:,}".format(round(cong_phat_sinh_no)), number_title_bold_style)
            sheet.write(y_offset, 8, "{:,}".format(round(cong_phat_sinh_co)), number_title_bold_style)
            sheet.write(y_offset, 9, "{:,}".format(round(cong_phat_sinh_balance)), number_title_bold_style)
            y_offset += 1
            sheet.write(y_offset, 5, "Số dư cuối kì", title_style)
            sheet.write(y_offset, 7, "{:,}".format(round(cuoi_ki_no)), number_title_bold_style)
            sheet.write(y_offset, 8, "{:,}".format(round(cuoi_ki_co)), number_title_bold_style)
            sheet.write(y_offset, 9, "{:,}".format(round(cuoi_ki_balance)), number_title_bold_style)
        # end print cuoi ki

        y_offset += 3
        sheet.write(y_offset, 7, 'Ngày ... tháng ... năm ...', default_style_bold)
        y_offset += 1
        sheet.write(y_offset, 2, "Người lập biểu", default_style_bold)
        sheet.write(y_offset, 5, "Kế toán trưởng", default_style_bold)
        sheet.write(y_offset, 7, "Giám đốc", default_style_bold)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file