# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz
from datetime import datetime, timedelta
from datetime import date
import logging
import json
import calendar
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import config, date_utils, get_lang
_logger = logging.getLogger(__name__)


class ReportAccountFinancialReport(models.AbstractModel):
    _inherit = 'account.financial.html.report'

    @api.model
    def _display_growth_comparison(self, options):
        is_comparison = super(ReportAccountFinancialReport, self)._display_growth_comparison(options)
        if 'report_name' in options:
            if options.get('report_name') == 'detail_report':
                is_comparison = False
        return is_comparison

    @api.model
    def _build_headers_hierarchy(self, options_list, groupby_keys):
        headers, sorted_groupby_keys = super(ReportAccountFinancialReport, self)._build_headers_hierarchy(options_list, groupby_keys)

        if self._context.get('print_mode'):
            for i in range(len(headers)):
                if i == 0:
                    headers[i][0] = {'name': 'Chỉ tiêu', 'style': 'width: 50%; text-align: right;'}
                    headers[i].insert(1, {'name': 'Mã', 'style': 'width: 20%; text-align: right;'})
                    if 'financial_id' in options_list[0]:
                        if options_list[0].get('financial_id') == 1:   # bao cao ket qua kinh doanh (P&L)
                            headers[i].insert(2, {'name': 'Thuyết minh', 'style': 'width: 20%; text-align: right;'})
                    # headers[i].insert(2, {'name': 'Số tiền', 'style': 'width: 30%; text-align: right;'})
        return headers, sorted_groupby_keys

    @api.model
    def _get_financial_line_report_line(self, options, financial_line, solver, groupby_keys):
        financial_report_line = super(ReportAccountFinancialReport, self)._get_financial_line_report_line(options, financial_line, solver, groupby_keys)
        if self._context.get('print_mode'):
            columns = financial_report_line.get('columns')
            financial_report_line['code']: financial_line.code
            columns.insert(0,
                {'name': financial_line.code if financial_line.code else ''})
            if 'financial_id' in options:
                if options.get('financial_id') == 1:  # P&L
                    columns.insert(1, {'name': ''})  # header thuyết minh

            financial_report_line['columns'] = columns

        return financial_report_line

    @api.model
    def _get_financial_aml_report_line(self, options, financial_report_line_id, financial_line, groupby_id, display_name, results, groupby_keys):
        financial_report_line = super(ReportAccountFinancialReport, self)._get_financial_aml_report_line(options, financial_report_line_id, financial_line, groupby_id, display_name, results, groupby_keys)
        if self._context.get('print_mode'):
            financial_report_line['code']: financial_line.code
            columns = financial_report_line.get('columns')
            financial_report_line['code']: financial_line.code
            columns.insert(0, {'name': financial_line.code if financial_line.code else ''})

            if 'financial_id' in options:
                if options.get('financial_id') == 1:  # P&L
                    columns.insert(1, {'name': financial_line.name if financial_line.name else ''})
        return financial_report_line

    def _get_reports_buttons(self, options):
        res = super(ReportAccountFinancialReport, self)._get_reports_buttons(options)
        res.append({'name': _('Export TT200'), 'action': 'export_detail_action', 'sequence': 8, 'file_export_type': _('XLSX')})
        return res

    def _update_comparison_filter(self, options, report, comparison_type, number_period, date_from=None, date_to=None):
        ''' Modify the existing options to set a new filter_comparison.
        :param options:         The report options.
        :param report:          The report.
        :param comparison_type: One of the following values: ('no_comparison', 'custom', 'previous_period', 'previous_year').
        :param number_period:   The number of period to compare.
        :param date_from:       A datetime object for the 'custom' comparison_type.
        :param date_to:         A datetime object the 'custom' comparison_type.
        :return:                The newly created options.
        '''
        report._init_filter_comparison(options, {**options, 'comparison': {
            'date_from': date_from and date_from.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'date_to': date_to and date_to.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'filter': comparison_type,
            'number_period': number_period,
        }})
        return options

    def export_detail_action(self, options):
        options['report_name'] = 'detail_report'
        options['financial_id'] = self.env.context.get('id')
        if ('comparison' not in options) or ('comparison' in options and options.get('comparison').get('filter') == 'no_comparison'):
            today = date.today()
            epoch_year = today.year
            date_from = date_utils.get_fiscal_year(today)[0]
            date_to = date(today.year, today.month, calendar.monthrange(today.year, today.month)[-1])
            self._update_comparison_filter(options=options, report=self, comparison_type='custom', number_period=1,
                                           date_from=date_from,
                                           date_to=date_to)
        # options['unfold_all'] = True
        return {
                'type': 'ir_actions_account_report_download',
                'data': {'model': self.env.context.get('model'),
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'financial_id': self.env.context.get('id'),
                         }
                }

    def get_xlsx(self, options, response=None):
        if 'report_name' in options:
            if options.get('report_name') == 'detail_report':
                return self.export_detail(options, response)
        return super(ReportAccountFinancialReport, self).get_xlsx(options, response)

    def export_detail(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        date_default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#000000', 'num_format': 'yyyy-mm-dd', 'border': 1})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#000000', 'num_format': 'yyyy-mm-dd', 'border': 1})
        default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#000000', 'border': 1})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#000000', 'border': 1})
        default_style1 = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': 0})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'border': 1,'fg_color':'#DDEBF7','font_size':10})
        level_0_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'border': 1, 'font_color': '#000000'})
        level_1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'border': 1, 'font_color': '#000000'})
        level_2_col1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#000000', 'border': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#000000', 'border': 1})
        level_2_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': '#000000', 'border': 1})
        level_3_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#000000', 'border': 1})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': 0, 'font_size': 10, 'font_color': '#000000', 'border': 1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': '#000000', 'border': 1})
        report_name_style = workbook.add_format({'font_name': 'Arial','font_size': 14, 'bold': True, 'font_color': 'red', 'align': 'center', 'valign': 'vcenter'})
        title_style_center = workbook.add_format({'font_name': 'Arial','font_size': 10, 'bold': 0, 'align': 'center', 'valign': 'vcenter'})
        title_style_center_bold = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter'})
        title_style_right = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'align': 'right', 'valign': 'vcenter'})
        number_title_bold_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'border': 1, 'align': 'right', 'border': 1})
        border_format = workbook.add_format({'border': 1, 'font_size': 10})

        # print company name
        y_offset = 0
        x_offset = 0
        sheet.fit_to_pages(1, 0)
        sheet.set_column(1, 1, 5)
        sheet.set_column(2, 3, 10)

        sheet.write(y_offset, x_offset, self.env.company.display_name, default_style1)
        y_offset += 1
        sheet.write(y_offset, x_offset, self.env.company.street, default_style1)
        # end print company name

        # get data
        # headers, lines = self.get_excel_table(options)

        y_offset += 3
        merge_from = 'A'
        merge_to = 'E'
        report_title = ''
        if self.id == 1:
            report_title = 'BÁO CÁO KẾT QUẢ KINH DOANH'
        elif self.id == 2:
            report_title = 'BẢNG CÂN ĐỐI KẾ TOÁN'

        sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset), report_title, report_name_style)
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        date_tmp = fields.Date.from_string(date_to)
        date_to = date_tmp.strftime('%d/%m/%Y')
        date_tmp = fields.Date.from_string(date_from)
        date_from = date_tmp.strftime('%d/%m/%Y')
        y_offset += 1
        sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset), 'Từ ngày ' + date_from + ' đến ngày ' + date_to,
                          title_style_center)

        # Set the first column width to 50
        sheet.set_column(0, 0, 50)
        y_offset += 1
        headers, lines = self.with_context(no_format=True, print_mode=True, prefetch_fields=False)._get_table(options)

        # Add headers.
        for header in headers:
            x_offset = 0
            for column in header:
                column_name_formated = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
                colspan = column.get('colspan', 1)
                if colspan == 1:
                    sheet.write(y_offset, x_offset, column_name_formated, title_style)
                else:
                    sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1, column_name_formated,
                                      title_style)
                x_offset += colspan
        # change default header
        y_temp = y_offset
        if 'financial_id' in options:
            if options.get('financial_id') == 1:  # P&L
                sheet.write(y_offset, 2, "Thuyết minh", title_style)
            #     sheet.write(y_offset, 3, "Năm nay", title_style)
            #     sheet.write(y_offset, 4, "Năm trước", title_style)
            elif options.get('financial_id') == 2:  # balance sheet
                sheet.write(y_offset, 2, "Số cuối năm", title_style)
                sheet.write(y_offset, 3, "Số đầu năm", title_style)
        y_offset += 1

        # Add lines.
        for y in range(0, len(lines)):
            level = lines[y].get('level')
            if lines[y].get('caret_options'):
                style = level_3_style
                col1_style = level_3_col1_style
                print(y_offset)
            elif level == 0:
                #y_offset += 1
                style = level_0_style
                col1_style = style
                print(y_offset)
            elif level == 1:
                style = level_1_style
                col1_style = style
            elif level == 2:
                style = level_2_style
                col1_style = 'total' in lines[y].get('class', '').split(
                    ' ') and level_2_col1_total_style or level_2_col1_style
            elif level == 3:
                style = level_3_style
                col1_style = 'total' in lines[y].get('class', '').split(
                    ' ') and level_3_col1_total_style or level_3_col1_style
            else:
                style = default_style
                col1_style = default_col1_style

            # write the first column, with a specific style to manage the indentation
            cell_type, cell_value = self._get_cell_type_value(lines[y])
            if cell_type == 'date':
                sheet.write_datetime(y + y_offset, 0, cell_value, date_default_col1_style)
            else:
                sheet.write(y + y_offset, 0, cell_value, col1_style)

            # write all the remaining cells
            for x in range(1, len(lines[y]['columns']) + 1):
                cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][x - 1])
                if cell_type == 'date':
                    sheet.write_datetime(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value,
                                         date_default_style)
                else:
                    sheet.write(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, style)
            if self.id == 1: #P&L
                sheet.conditional_format('A%d:E%d' %(y_temp+1, y_offset+y+1), {'type':'blanks', 'format': border_format})
            elif self.id == 2:
                sheet.conditional_format('A%d:D%d' %(y_temp+1, y_offset+y+1), {'type':'blanks', 'format': border_format})

        y_offset += y + 3
        sheet.write(y_offset, 3, 'Ngày ... tháng ... năm ...', default_style1)
        y_offset += 1
        sheet.write(y_offset, 0, "Người lập biểu                 Kế toán trưởng ", title_style_center_bold)
        sheet.write(y_offset, 3, "Giám đốc", title_style_center_bold)
        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file
