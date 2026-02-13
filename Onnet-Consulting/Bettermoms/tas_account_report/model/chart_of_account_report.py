# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from copy import deepcopy

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz
from datetime import datetime, timedelta
import json


class AccountChartOfAccountReport(models.AbstractModel):
    _inherit = "account.coa.report"

    def _get_reports_buttons(self, options):
        res = super(AccountChartOfAccountReport, self)._get_reports_buttons(options)
        res.append({'name': _('Xuất chi tiết tài khoản'), 'action': 'export_detail_action', 'sequence': 8, 'file_export_type': _('XLSX')})
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

    def get_excel_table(self, options):
        ctx = {'no_format': True, 'print_excel_mode': True, 'prefetch_fields': False}
        headers, lines = self.with_context(ctx)._get_table(options)
        headers = [[
                {'name': _('Ngày'), 'class': 'date'},
                {'name': _('Chứng từ')},
                {'name': _('Diễn giải')},
                {'name': _('Tk đối ứng')},
                {'name': _('Nợ'), 'class': 'number'},
                {'name': _('Có'), 'class': 'number'},
                {'name': _('Nợ'), 'class': 'number'},
                {'name': _('Có'), 'class': 'number'},
                {'name': _('Số HĐ')},
                {'name': _('Ngày HĐ'), 'class': 'date'},
                {'name': _('Mã KH')},
                {'name': _('Tên KH')},
                {'name': _('TK')},
                {'name': _('Tên chi nhánh')}]]

        return headers, lines

    def get_xlsx(self, options, response=None):
        if 'report_name' in options:
            if options.get('report_name') == 'detail_report':
                return self.export_detail(options, response)
        return super(AccountChartOfAccountReport, self).get_xlsx(options, response)

    def export_detail(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        date_default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10,  'num_format': 'yyyy-mm-dd', 'border': 1})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10,  'num_format': 'yyyy-mm-dd', 'border': 1})
        default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10})
        default_style_bold = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'border': 1,'font_size':10, 'font_color':'blue'})
        level_0_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'bottom': 6, })
        level_1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'bottom': 1, })
        level_2_col1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'indent': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, })
        level_2_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, })
        level_3_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, })
        level_3_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': 0, 'font_size': 10, 'align':'justify', 'border':1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'border': 1})
        report_name_style = workbook.add_format({'font_name': 'Arial','font_size': 14, 'bold': True, 'font_color': 'red', 'align': 'center', 'valign': 'vcenter'})
        title_style_center = workbook.add_format({'font_name': 'Arial','font_size': 10, 'bold': 0, 'align': 'center', 'valign': 'vcenter'})
        title_style_center_border = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'border':1,'fg_color':'#DDEBF7'})
        number_title_bold_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'border': 1, 'align': 'right','font_size':10, 'font_color':'blue'})
        border_format = workbook.add_format({'border':1})



        # print company name
        y_offset = 0
        x_offset = 0
        sheet.set_column(0, 13, 8)
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 20)
        sheet.set_column(10, 11, 15)
        sheet.set_column(13, 13, 15)

        sheet.fit_to_pages(1, 0)
        y_offset += 1
        sheet.merge_range('A%d:J%d' %(y_offset, y_offset), self.env.company.display_name, default_style)
        y_offset += 1
        sheet.merge_range('A%d:J%d' %(y_offset, y_offset), self.env.company.street, default_style)
        # end print company name

        # get data
        headers, lines = self.get_excel_table(options)
        date_from = fields.Date.from_string(options.get('date').get('date_from'))
        date_to = fields.Date.from_string(options.get('date').get('date_to'))
        move_lines = self.env['account.move.line'].search([
            ('account_id', '!=', False),
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        account_dict = {}
        for move_line in move_lines:
            if move_line.account_id.id in account_dict:
                account_dict[move_line.account_id.id].append(move_line)
            else:
                account_dict[move_line.account_id.id] = [move_line]

        for y in range(0, len(lines) - 1):
            y_offset += 3
            merge_from = 'A'
            merge_to = 'N'
            sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset), 'SỔ CHI TIẾT TÀI KHOẢN',
                              report_name_style)
            y_offset += 1
            sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset),
                              'Từ ngày ' + datetime.strptime(options.get('date').get('date_from'), "%Y-%m-%d").strftime("%d/%m/%Y") + ' Đến ngày ' + datetime.strptime(options.get('date').get('date_to'), "%Y-%m-%d").strftime("%d/%m/%Y"), title_style_center)
            y_offset += 1
            sheet.merge_range(merge_from + str(y_offset) + ':' + merge_to + str(y_offset),
                              'Tài khoản: ' + lines[y].get('name'), title_style_center)
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
                        sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1,
                                          column_name_formated,
                                          title_style_center_border)
                    x_offset += colspan
            # end print header
            y_offset += 1
            y_temp = y_offset
            sheet.write(y_offset, 2, "Số dư đầu kì", title_style)
            sheet.write(y_offset, 4, "0", number_title_bold_style)
            sheet.write(y_offset, 5, "0", number_title_bold_style)
            cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][0])
            du_no = int(cell_value) if cell_value else 0
            sheet.write(y_offset, 6, cell_value, number_title_bold_style)
            cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][1])
            du_co = int(cell_value) if cell_value else 0
            sheet.write(y_offset, 7, cell_value, number_title_bold_style)

            y_offset += 1
            journal_items = account_dict[int(lines[y]['id'])] if int(lines[y]['id']) in account_dict else []
            for journal_item in journal_items:
                sheet.write(y_offset, 0, journal_item.date.strftime('%d/%m/%Y'), date_default_col1_style)
                sheet.write(y_offset, 1, journal_item.move_name, level_3_style)
                sheet.write(y_offset, 2, journal_item.name if journal_item.name else '', level_3_col1_total_style)
                sheet.write(y_offset, 3, journal_item.countered_accounts, level_3_style)
                ps_no = journal_item.debit
                sheet.write(y_offset, 4, ps_no, level_3_style)
                ps_co = journal_item.credit
                sheet.write(y_offset, 5, ps_co, level_3_style)

                print("journal item " + str(journal_item.name))
                du_no_tren = du_no
                du_co_tren = du_co

                print("du no tren " + str(du_no_tren))
                print("du co tren " + str(du_co_tren))
                du_no = (du_no_tren - du_co_tren) + (ps_no - ps_co) if (du_no_tren - du_co_tren) + (ps_no - ps_co) > 0 else 0

                print("du no " + str(du_no))
                sheet.write(y_offset, 6, du_no, level_3_style)

                du_co = (du_co_tren - du_no_tren) + (ps_co - ps_no) if  (du_co_tren - du_no_tren) + (ps_co - ps_no) > 0 else 0

                print("du co " + str(du_co))
                sheet.write(y_offset, 7, du_co, level_3_style)

                sheet.write(y_offset, 8, journal_item.einvoice_number, level_3_style)
                sheet.write(y_offset, 9, journal_item.einvoice_date.strftime('%d/%m/%Y') if journal_item.einvoice_date else '', date_default_col1_style)

                # get customer name
                customerName = ''

                if journal_item.move_id.move_type == 'in_invoice':
                    customerName = journal_item.partner_id.name if journal_item.partner_id and journal_item.partner_id.name else journal_item.partner_id.customerName
                elif journal_item.move_id.move_type == 'out_invoice':
                    if journal_item.partner_id and journal_item.partner_id.company_type == 'company':
                        customerName = journal_item.partner_id.name
                    elif journal_item.partner_id and journal_item.partner_id.company_type == 'employer':
                        customerName = journal_item.partner_id.customerName if journal_item.partner_id.customerName else journal_item.partner_id.name
                customerCode = journal_item.partner_id.ref if journal_item.partner_id and journal_item.partner_id.ref else ''
                sheet.write(y_offset, 10, customerCode, level_3_col1_total_style)
                sheet.write(y_offset, 11, customerName, level_3_col1_total_style)
                sheet.write(y_offset, 12, journal_item.account_id.code, level_3_col1_total_style)

                # get branch name
                branch_name = ''
                if journal_item.move_id.move_type == 'in_invoice':
                    branch_name = journal_item.move_id.company_branch_vat.name if journal_item.move_id.company_branch_vat else ''
                elif journal_item.move_id.move_type == 'out_invoice':
                    branch_name = journal_item.move_id.company_branch_id.name if journal_item.move_id.company_branch_id else ''

                sheet.write(y_offset, 13, branch_name, level_3_col1_total_style)
                y_offset += 1

            sheet.write(y_offset, 2, "Cộng phát sinh", title_style)
            cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][2])
            sheet.write(y_offset, 4, cell_value, number_title_bold_style)
            cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][3])
            sheet.write(y_offset, 5, cell_value, number_title_bold_style)
            y_offset += 1
            sheet.write(y_offset, 2, "Số dư cuối kì", title_style)
            cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][4])
            sheet.write(y_offset, 6, cell_value, number_title_bold_style)
            cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][5])
            sheet.write(y_offset, 7, cell_value, number_title_bold_style)
            sheet.conditional_format('A%d:N%d' % (y_temp,y_offset+1), {'type':'blanks', 'format': border_format})

        y_offset += 3
        sheet.write(y_offset, 8, 'Ngày ... tháng ... năm ...', default_style)
        y_offset += 1
        sheet.write(y_offset, 2, "Người lập biểu", default_style_bold)
        sheet.write(y_offset, 5, "Kế toán trưởng", default_style_bold)
        sheet.write(y_offset, 9, "Giám đốc", default_style_bold)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file