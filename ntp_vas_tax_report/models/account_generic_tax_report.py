# __author__ = 'BinhTT'
from odoo import fields, api, models, _
import io
import xlsxwriter
import logging
_logger = logging.getLogger(__name__)
from datetime import datetime
import json
class NTPAccountGenericTaxReport(models.AbstractModel):
    _inherit = 'account.generic.tax.report'


    def _get_reports_buttons(self, options):
        res = super(NTPAccountGenericTaxReport, self)._get_reports_buttons(options)
        res.append({'name': _('VAS SUMMARY XLSX'), 'action': 'export_summary_action', 'sequence': 3, 'file_export_type': _('XLSX')})
        res.append({'name': _('VAS DETAIL XLSX'), 'action': 'export_detail_action', 'sequence': 3, 'file_export_type': _('XLSX')})
        return res

    def export_summary_action(self, options):
        options['report_name'] = 'summary_report'
        options['skip_base'] = True
        return {
                'type': 'ir_actions_account_report_download',
                'data': {'model': self.env.context.get('model'),
                         'options': json.dumps(options),
                         'output_format': 'vas_xlsx',
                         'financial_id': self.env.context.get('id'),
                         }
                }

    def export_detail_action(self, options):
        options['report_name'] = 'detail_report'
        options['skip_base'] = True
        return {
                'type': 'ir_actions_account_report_download',
                'data': {'model': self.env.context.get('model'),
                         'options': json.dumps(options),
                         'output_format': 'vas_xlsx',
                         'financial_id': self.env.context.get('id'),
                         }
                }

    def get_vas_detail_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })

        data = self.get_sql_detail_vas_report(options)
        report_id = self.env['account.tax.report'].browse(options.get('tax_report'))
        for report_sheet in report_id.root_line_ids:
            sheet = workbook.add_worksheet(report_sheet.name)
            date_default_col1_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'indent': 2,
                 'num_format': 'yyyy-mm-dd'})
            date_default_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd'})
            default_col1_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
            default_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666'})
            title_style = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_color': '#000080',
                                               'align': 'vcenter', 'text_wrap': 'wrap', 'align': 'center'})
            title_style_bold_left = workbook.add_format({'font_name': 'Times New Roman', 'bold': True,
                                                         'font_size': 10, 'font_color': '#000080', 'align': 'left'})
            title_style_bold_left_black = workbook.add_format({'font_name': 'Times New Roman', 'bold': True,
                                                               'font_size': 10, 'align': 'left'})

            style_left_black = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10, 'align': 'left'})
            style_right_black = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10, 'align': 'right'})

            title_style_no_bold = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_color': '#000080', 'font_size': 10, 'align': 'center'})
            title_style_no_bold_right = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_color': '#000080', 'font_size': 10, 'align': 'right'})
            full_border = workbook.add_format({'top': 1, 'left': 1, 'bottom': 1, 'right': 1})
            level_0_style = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                                                 'top': 1, 'right': 3, 'bottom': 3, 'left': 3,
                                                 'bg_color': '#C0C0C0', 'align': 'center'})
            level_0_style_bordertop_right = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'top': 1, 'right': 1, 'bottom': 3, 'left': 3,
                 'bg_color': '#C0C0C0', 'align': 'center'})
            level_0_style_bordertop_left = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'top': 1, 'left': 1, 'bottom': 3, 'right': 3,
                 'bg_color': '#C0C0C0', 'align': 'center'})
            level_1_style_left = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                                                      'top': 3, 'left': 1, 'bottom': 3, 'right': 3, })
            level_1_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'text_wrap': 'wrap', 'num_format': '#,##0'})
            level_1_style_bottom = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter',
                 'top': 3, 'left': 3, 'bottom': 1, 'right': 3, 'text_wrap': 'wrap'})
            level_1_style_right = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 1, 'num_format': '#,##0'})

            level_1_style_right_center = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'bg_color': '#F0F0F0', 'align': 'center',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
            level_1_style_borderleft_center = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 1, 'bottom': 3, 'right': 3, 'align': 'center', })
            level_1_style_borderlefbottom_center = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 1, 'bottom': 1, 'right': 3, 'align': 'center', })
            level_1_style_center = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'align': 'center', 'align': 'vcenter',
                 'num_format': '#,##0'})

            level_1_style_center_blue = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'bg_color': '#CCFFFF',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'align': 'center', })
            level_1_style_right_center_blue = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'bg_color': '#CCFFFF', 'align': 'center',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
            level_1_style_right_blue = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#CCFFFF',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
            level_1_style_left_center_blue = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                 'bg_color': '#CCFFFF',
                 'top': 3, 'left': 1, 'bottom': 3, 'right': 3, 'align': 'center', })
            level_1_style_blue = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#CCFFFF',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 3, })
            level_2_style_left = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10,
                                                      'top': 3, 'left': 1, 'bottom': 3, 'right': 3, })
            level_2_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'text_wrap': 'wrap'})
            level_2_style_right = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
            level_2_style_borderbottomright = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 3, 'bottom': 1, 'right': 1, })
            level_2_style_borderleft_center = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0',
                 'top': 3, 'left': 1, 'bottom': 3, 'right': 3, 'align': 'center', })
            level_2_style_center = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 10,
                 'bg_color': '#F0F0F0', 'text_wrap': 'wrap',
                 'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'align': 'center', })
            level_2_style_bottom = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter',
                 'align': 'center',
                 'top': 3, 'left': 3, 'bottom': 1, 'right': 3, 'text_wrap': 'wrap'})
            level_3_col1_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
            level_3_col1_total_style = workbook.add_format(
                {'font_name': 'Times New Roman', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
            level_3_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666'})

            #Set the first column width to 50
            sheet.set_row(0, 50)
            sheet.set_column(0, 0, 3.5)

            y_offset = 0
            headers, lines = self.with_context(no_format=True, print_mode=True, prefetch_fields=False)._get_table(options)
            # Add headers.
            for header in headers:
                x_offset = 1
                for column in header:
                    column_name_formated = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
                    colspan = column.get('colspan', 1)
                    if colspan == 1:
                        sheet.write(y_offset, x_offset, column_name_formated, title_style)
                    else:
                        sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1, column_name_formated, title_style)
                    x_offset += colspan
                y_offset += 1
            # line 2:
            sheet.write(y_offset, 6, '[01] Kỳ tính thuế:', title_style_no_bold_right)
            sheet.merge_range(y_offset, 7, y_offset, 14, 'Quý .. năm %s' % (datetime.now().year), title_style_no_bold)
            # line3
            y_offset += 1
            sheet.merge_range(y_offset, 6, y_offset, 7, '[02] Lần đầu:  ', title_style_no_bold)
            sheet.write(y_offset, 8, '', full_border)
            sheet.write(y_offset, 9, '[03] Bổ sung lần thứ:', title_style_no_bold)
            sheet.write(y_offset, 10, '', full_border)
            # line 4
            y_offset += 1
            sheet.merge_range(y_offset, 1, y_offset, 2, '[04] Tên người nộp thuế:', title_style_bold_left)
            sheet.merge_range(y_offset, 3, y_offset, 11, self.env.company.name.upper(), title_style_bold_left)
            # line 5
            y_offset += 1
            sheet.merge_range(y_offset, 1, y_offset, 2, '[05] Mã số thuế:', title_style_bold_left)
            sheet.merge_range(y_offset, 3, y_offset, 11, self.env.company.vat.upper(), title_style_bold_left)
            # line 6
            y_offset += 1
            sheet.merge_range(y_offset, 1,  y_offset, 2, 'Hoá Đơn', level_0_style_bordertop_left)
            sheet.write(y_offset, 3,  'Ngày', level_0_style)
            sheet.merge_range(y_offset, 4, y_offset, 6, 'Tên', level_0_style_bordertop_left)
            sheet.write(y_offset, 7,  'Mã Số Thuế', level_0_style)

            sheet.merge_range(y_offset, 8, y_offset, 10, 'Chi Tiết', level_0_style_bordertop_left)
            sheet.merge_range(y_offset, 11, y_offset, 12, 'GIÁ TRỊ HHDV', level_0_style)
            sheet.merge_range(y_offset, 13, y_offset, 14, 'VAT', level_0_style)
            sheet.merge_range(y_offset, 15, y_offset, 16, 'THUẾ GTGT', level_0_style_bordertop_right)
            sheet.merge_range(y_offset, 17, y_offset, 18, 'Tổng', level_0_style_bordertop_right)
            stt = 0
            for r in data:
                if r.get('root_tax_name') != report_sheet.name:
                    continue
                y_offset += 1
                stt += 1
                sheet.merge_range(y_offset, 1,  y_offset, 2, r.get('invocie_name', ''), level_1_style_borderleft_center)
                sheet.write(y_offset, 3, r.get('date', '').strftime('%Y-%m-%d') if r.get('date', '') else '', level_1_style)
                sheet.merge_range(y_offset, 4, y_offset, 6, r.get('partner_name', ''), level_1_style)
                sheet.write(y_offset, 7, r.get('tax_code'), level_1_style)
                sheet.merge_range(y_offset, 8, y_offset, 10,  r.get('move_name', ''), level_1_style)
                sheet.merge_range(y_offset, 11, y_offset, 12, r.get('untax_balance', ''), level_1_style)
                sheet.merge_range(y_offset, 13, y_offset, 14, r.get('percent_name', ''), level_1_style)
                sheet.merge_range(y_offset, 15, y_offset, 16, r.get('tax', ''), level_1_style_right)
                sheet.merge_range(y_offset, 17, y_offset, 18,(r.get('untax_balance') or 0)+ (r.get('tax', 0) or 0), level_1_style_right)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file
    def get_vas_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        date_default_col1_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'indent': 2, 'num_format': 'yyyy-mm-dd'})
        date_default_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd'})
        default_col1_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_color': '#000080',
                                           'align': 'vcenter', 'text_wrap': 'wrap', 'align': 'center'})
        title_style_bold_left = workbook.add_format({'font_name': 'Times New Roman', 'bold': True,
                                                     'font_size': 10, 'font_color': '#000080', 'align': 'left'})
        title_style_bold_left_black = workbook.add_format({'font_name': 'Times New Roman', 'bold': True,
                                                     'font_size': 10, 'align': 'left'})

        style_left_black = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10, 'align': 'left'})
        style_right_black = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10, 'align': 'right'})

        title_style_no_bold = workbook.add_format({'font_name': 'Times New Roman', 'font_color': '#000080','font_size': 10,'align': 'center'})
        title_style_no_bold_right = workbook.add_format({'font_name': 'Times New Roman', 'font_color': '#000080','font_size': 10,'align': 'right'})
        full_border = workbook.add_format({'top': 1, 'left': 1, 'bottom': 1, 'right': 1})
        level_0_style = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                                             'top': 1, 'right': 3, 'bottom': 3, 'left': 3,
                                             'bg_color': '#C0C0C0', 'align': 'center'})
        level_0_style_bordertop_right = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                                                       'top': 1, 'right': 1, 'bottom': 3, 'left': 3,
                                                       'bg_color': '#C0C0C0','align': 'center'})
        level_0_style_bordertop_left = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                                                      'top': 1, 'left': 1, 'bottom': 3, 'right': 3,
                                                      'bg_color': '#C0C0C0','align': 'center'})
        level_1_style_left = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
                                                  'top': 3, 'left': 1, 'bottom': 3, 'right': 3,})
        level_1_style = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'text_wrap': 'wrap'})
        level_1_style_bottom = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter',
             'top': 3, 'left': 3, 'bottom': 1, 'right': 3, 'text_wrap': 'wrap'})
        level_1_style_right = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,  'bg_color': '#F0F0F0',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 1, 'num_format': '#,##0'})

        level_1_style_right_center = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
             'bg_color': '#F0F0F0', 'align': 'center',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
        level_1_style_borderleft_center = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,'bg_color': '#F0F0F0',
             'top': 3, 'left': 1, 'bottom': 3, 'right': 3, 'align': 'center', })
        level_1_style_borderlefbottom_center = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,'bg_color': '#F0F0F0',
             'top': 3, 'left': 1, 'bottom': 1, 'right': 3, 'align': 'center', })
        level_1_style_center = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
             'bg_color': '#F0F0F0',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'align': 'center', 'align': 'vcenter', 'num_format': '#,##0'})

        level_1_style_center_blue = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
             'bg_color': '#CCFFFF',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'align': 'center', })
        level_1_style_right_center_blue = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
             'bg_color': '#CCFFFF', 'align': 'center',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
        level_1_style_right_blue = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#CCFFFF',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
        level_1_style_left_center_blue = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10,
             'bg_color': '#CCFFFF',
             'top': 3, 'left': 1, 'bottom': 3, 'right': 3, 'align': 'center', })
        level_1_style_blue = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'bg_color': '#CCFFFF',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 3, })
        level_2_style_left = workbook.add_format({'font_name': 'Times New Roman',  'font_size': 10,
                                                  'top': 3, 'left': 1, 'bottom': 3, 'right': 3, })
        level_2_style = workbook.add_format(
            {'font_name': 'Times New Roman',  'font_size': 10, 'bg_color': '#F0F0F0',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'text_wrap': 'wrap'})
        level_2_style_right = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 1, })
        level_2_style_borderbottomright = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bg_color': '#F0F0F0',
             'top': 3, 'left': 3, 'bottom': 1, 'right': 1, })
        level_2_style_borderleft_center = workbook.add_format(
            {'font_name': 'Times New Roman',  'font_size': 10, 'bg_color': '#F0F0F0',
             'top': 3, 'left': 1, 'bottom': 3, 'right': 3, 'align': 'center', })
        level_2_style_center = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10,
             'bg_color': '#F0F0F0', 'text_wrap': 'wrap',
             'top': 3, 'left': 3, 'bottom': 3, 'right': 3, 'align': 'center', })
        level_2_style_bottom = workbook.add_format(
            {'font_name': 'Times New Roman',  'font_size': 10, 'bg_color': '#F0F0F0', 'align': 'vcenter', 'align': 'center',
             'top': 3, 'left': 3, 'bottom': 1, 'right': 3, 'text_wrap': 'wrap'})
        level_3_col1_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 12, 'font_color': '#666666'})

        #Set the first column width to 50
        sheet.set_row(0, 50)
        sheet.set_column(0, 0, 3.5)
        sheet.set_column(1, 1, 6)
        sheet.set_column(2, 2, 14)
        sheet.set_column(3, 5, 3)
        sheet.set_column(6, 6, 14)
        sheet.set_column(7, 7, 2)
        sheet.set_column(8, 8, 4)
        sheet.set_column(9, 9, 16)
        sheet.set_column(10, 10, 4)
        sheet.set_column(11, 11, 16)

        y_offset = 0
        headers, lines = self.with_context(no_format=True, print_mode=True, prefetch_fields=False)._get_table(options)
        # Add headers.
        for header in headers:
            x_offset = 1
            for column in header:
                column_name_formated = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
                colspan = column.get('colspan', 1)
                if colspan == 1:
                    sheet.write(y_offset, x_offset, column_name_formated, title_style)
                else:
                    sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1, column_name_formated, title_style)
                x_offset += colspan
            y_offset += 1

        # line 2:
        sheet.write(y_offset, 6, '[01] Kỳ tính thuế:', title_style_no_bold_right)
        sheet.merge_range(y_offset, 7, y_offset, 14, 'Quý .. năm %s'% (datetime.now().year), title_style_no_bold)
        # line3
        y_offset += 1
        sheet.merge_range(y_offset, 6, y_offset, 7, '[02] Lần đầu:  ', title_style_no_bold)
        sheet.write(y_offset, 8, '', full_border)
        sheet.write(y_offset, 9, '[03] Bổ sung lần thứ:', title_style_no_bold)
        sheet.write(y_offset, 10, '', full_border)
        # line 4
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[04] Tên người nộp thuế:', title_style_bold_left)
        sheet.merge_range(y_offset, 3, y_offset, 11, self.env.company.name.upper(), title_style_bold_left)
        # line 5
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[05] Mã số thuế:', title_style_bold_left)
        sheet.merge_range(y_offset, 3, y_offset, 11, self.env.company.vat.upper(), title_style_bold_left)

        # line 6
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[12] Tên đại lý thuế (nếu có):', title_style_bold_left)

        # line 7
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[13] Mã số thuế đại lý:', title_style_bold_left)

        # line 8
        y_offset += 1
        sheet.write(y_offset, 1,  '', full_border)
        sheet.merge_range(y_offset, 2, y_offset, 11,  '  Gia hạn', title_style_bold_left)
        # line 8,9
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2,  'Trường hợp được gia hạn:', title_style_bold_left)
        sheet.merge_range(y_offset, 3, y_offset, 11,  ' ', full_border)
        y_offset += 1

        sheet.set_row(y_offset, 5)

        # line 10
        y_offset += 1
        sheet.write(y_offset, 1,  'STT', level_0_style_bordertop_left)
        sheet.merge_range(y_offset, 2, y_offset, 7,  'CHỈ TIÊU', level_0_style)
        sheet.merge_range(y_offset, 8, y_offset, 9,  'GIÁ TRỊ HHDV', level_0_style)
        sheet.merge_range(y_offset, 10, y_offset, 11,  'THUẾ GTGT', level_0_style_bordertop_right)
        # line 11
        y_offset += 1
        sheet.write(y_offset, 1,  'A', level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7,  'Không phát sinh hoạt động mua, bán trong kỳ (đánh dấu "X")', level_1_style)
        sheet.write(y_offset, 8,  '[21]', level_1_style_center)
        sheet.write(y_offset, 9,  '', level_1_style)
        sheet.merge_range(y_offset, 10, y_offset, 11,  '', level_1_style_right)

        # line 12
        y_offset += 1
        sheet.write(y_offset, 1, 'B', level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9, 'Thuế GTGT còn được khấu trừ kỳ trước chuyển sang',
                          level_1_style)
        sheet.write(y_offset, 10, '[22]', level_1_style_center)
        sheet.write(y_offset, 11, lines.get('22', ''), level_1_style_right)
        # line 13
        y_offset += 1
        sheet.write(y_offset, 1, 'C', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 11, 'Kê khai thuế GTGT phải nộp Ngân sách nhà nước',
                          level_1_style_right_blue)
        # line 14
        y_offset += 1
        sheet.write(y_offset, 1, 'I', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 11, 'Hàng hóa, dịch vụ (HHDV) mua vào trong kỳ',
                          level_1_style_right_blue)

        # line 15
        y_offset += 1
        sheet.write(y_offset, 1, 1, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Giá trị và thuế GTGT của hàng hóa, dịch vụ mua vào',
                          level_1_style)
        sheet.write(y_offset, 8, '[23]', level_1_style_center)
        sheet.write(y_offset, 9, lines.get('23', ''), level_1_style_center)
        sheet.write(y_offset, 10, '[24]', level_1_style_center)
        sheet.write(y_offset, 11, lines.get('24', ''), level_1_style_right)
        # line 16
        y_offset += 1
        sheet.write(y_offset, 1, 2, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9, 'Tổng số thuế GTGT  được khấu trừ kỳ này',
                          level_1_style_right)
        sheet.write(y_offset, 10, '[25]', level_1_style_center)
        sheet.write(y_offset, 11, '', level_1_style_right)
        # line 17
        y_offset += 1
        sheet.write(y_offset, 1, 'II', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 11, 'Hàng hóa, dịch vụ bán ra trong kỳ												',
                          level_1_style_right_blue)
        # line 18
        y_offset += 1
        sheet.write(y_offset, 1, 1, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Hàng hóa, dịch vụ bán ra không chịu thuế GTGT ',
                          level_1_style)
        sheet.write(y_offset, 8, '[26]', level_1_style_center)
        sheet.write(y_offset, 9, '', level_1_style_center)
        sheet.merge_range(y_offset, 10, y_offset, 11, '', level_1_style_right)
        # line 19
        y_offset += 1
        sheet.set_row(y_offset, 30)

        sheet.write(y_offset, 1, 2, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Hàng hóa, dịch vụ bán ra chịu thuế GTGT \n'
                                                    '([27] = [29] + [30] + [32] +[32a]; [28] = [31] + [33]) ',
                          level_1_style)
        sheet.write(y_offset, 8, '[27]', level_1_style_center)
        # lines.update({'27': lines.get('29', 0) + lines.get('30', 0) + lines.get('32', 0) })
        # lines.update({'28': lines.get('31', 0) + lines.get('33', 0) })
        sheet.write_formula(y_offset, 9, '=J21+J22+J23+J24', level_1_style_center)
        sheet.write(y_offset, 10, '[28]', level_1_style_center)
        sheet.write_formula(y_offset, 11, '=L22+L23', level_1_style_right)
        # line 20
        y_offset += 1
        sheet.write(y_offset, 1, 'a', level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Hàng hóa, dịch vụ bán ra chịu thuế suất 0%',
                          level_2_style)
        sheet.write(y_offset, 8, '[29]', level_2_style_center)
        sheet.write(y_offset, 9, lines.get('29', ''), level_1_style_center)
        sheet.write(y_offset, 10, '', level_2_style_center)
        sheet.write(y_offset, 11, '', level_2_style_center)

        # line 21
        y_offset += 1
        sheet.write(y_offset, 1, 'b', level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Hàng hóa, dịch vụ bán ra chịu thuế suất 5%',
                          level_2_style)
        sheet.write(y_offset, 8, '[30]', level_2_style_center)
        sheet.write(y_offset, 9, lines.get('30', ''), level_1_style_center)
        sheet.write(y_offset, 10, '[31]', level_2_style_center)
        sheet.write(y_offset, 11, lines.get('31', ''), level_2_style_right)
        # line 22
        y_offset += 1
        sheet.write(y_offset, 1, 'c', level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Hàng hóa, dịch vụ bán ra chịu thuế suất 10%',
                          level_2_style)
        sheet.write(y_offset, 8, '[32]', level_2_style_center)
        sheet.write(y_offset, 9, lines.get('32', ''), level_1_style_center)
        sheet.write(y_offset, 10, '[33]', level_2_style_center)
        sheet.write(y_offset, 11,  lines.get('33', ''), level_2_style_right)
        # line 23
        y_offset += 1
        sheet.write(y_offset, 1, 'd', level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Hàng hóa, dịch vụ bán ra không tính thuế',
                          level_2_style)
        sheet.write(y_offset, 8, '[32a]', level_2_style_center)
        sheet.write(y_offset, 9, lines.get('32a', ''), level_1_style_center)
        sheet.write(y_offset, 10, '', level_2_style_center)
        sheet.write(y_offset, 11, '', level_2_style_right)
        # line 24
        y_offset += 1
        sheet.set_row(y_offset, 30)
        sheet.write(y_offset, 1, 3, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 7, 'Tổng doanh thu và thuế GTGT của HHDV bán  ra \n([34] = [26] + [27]; [35] = [28])',
                          level_1_style)
        sheet.write(y_offset, 8, '[34]', level_1_style_center)
        sheet.write_formula(y_offset, 9,'=J19+J20', level_1_style_center)
        sheet.write(y_offset, 10, '[35]', level_1_style_center)
        sheet.write_formula(y_offset, 11, '=L20', level_1_style_right)

        # line 25
        y_offset += 1
        sheet.write(y_offset, 1, 'III', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT phát sinh trong kỳ ([36] = [35] - [25])',
                          level_1_style_blue)
        sheet.write(y_offset, 10, '[36]', level_1_style_blue)
        sheet.write_formula(y_offset, 11, '=L25-L17', level_1_style_right)
        # line 26
        y_offset += 1
        sheet.write(y_offset, 1, 'IV', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 11,
                          'Điều chỉnh tăng, giảm thuế GTGT còn được khấu trừ của các kỳ trước 							',
                          level_1_style_right_blue)
        # line 27
        y_offset += 1
        sheet.write(y_offset, 1, 1, level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9, 'Điều chỉnh giảm ',
                          level_2_style)
        sheet.write(y_offset, 10, '[37]', level_2_style_center)
        sheet.write(y_offset, 11, 0, level_2_style_right)
        # line 28
        y_offset += 1
        sheet.write(y_offset, 1, 2, level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9, 'Điều chỉnh tăng ',
                          level_2_style)
        sheet.write(y_offset, 10, '[38]', level_2_style_center)
        sheet.write(y_offset, 11, 0, level_2_style_right)
        # line 29
        y_offset += 1
        sheet.write(y_offset, 1, 'V', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT đã nộp ở địa phương khác của hoạt động kinh doanh xây dựng, lắp đặt, bán hàng, bất động sản ngoại tỉnh',
                          level_1_style_blue)
        sheet.write(y_offset, 10, '[39]', level_1_style_blue)
        sheet.write(y_offset, 11, '', level_1_style_right)
        # line 30
        y_offset += 1
        sheet.write(y_offset, 1, 'VI', level_1_style_left_center_blue)
        sheet.merge_range(y_offset, 2, y_offset, 15,
                          'Xác định nghĩa vụ thuế GTGT phải nộp trong kỳ:',
                          level_1_style_blue)
        # line 31
        y_offset += 1
        sheet.set_row(y_offset, 30)
        sheet.write(y_offset, 1, 1, level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9, 'Thuế GTGT phải nộp của hoạt động sản xuất kinh doanh trong kỳ ([40a] = [36] - [22] + [37] - [38] - [39] ≥ 0)',
                          level_2_style)
        sheet.write(y_offset, 10, '[40a]', level_2_style_center)
        sheet.write_formula(y_offset, 11, '=L26-L13+L28-L29-L30', level_2_style_right)
        # line 32
        y_offset += 1
        sheet.set_row(y_offset, 30)
        sheet.write(y_offset, 1, 2, level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT mua vào của dự án đầu tư (cùng tỉnh, thành phố trực thuộc trung ương) được bù trừ với thuế GTGT còn phải nộp của hoạt động sản xuất kinh doanh cùng kỳ tính thuế',
                          level_2_style)
        sheet.write(y_offset, 10, '[40b]', level_2_style_center)
        sheet.write(y_offset, 11, 0, level_2_style_right)

        # line 33
        y_offset += 1
        sheet.write(y_offset, 1, 3, level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT còn phải nộp trong kỳ ([40] = [40a] - [40b])',
                          level_2_style)
        sheet.write(y_offset, 10, '[40]', level_2_style_center)
        sheet.write_formula(y_offset, 11, '=L32-L33', level_2_style_right)

        # line 35
        y_offset += 1
        sheet.write(y_offset, 1, 4, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT chưa khấu trừ hết kỳ này (nếu ([41] = [36] - [22] + [37] - [38] - [39] < 0)',
                          level_1_style)
        sheet.write(y_offset, 10, '[41]', level_2_style_center)
        sheet.write_formula(y_offset, 11, '=IF((L26-L13+L28-L29-L30 < 0), L26-L13+L28-L29-L30, 0)', level_2_style_right)

        # line 36
        y_offset += 1
        sheet.write(y_offset, 1, 4.1, level_1_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Tổng số thuế GTGT đề nghị hoàn',
                          level_1_style)
        sheet.write(y_offset, 10, '[42]', level_2_style_center)
        sheet.write_formula(y_offset, 11, '=L37+L38', level_2_style_right)

        # line 37
        y_offset += 1
        sheet.write(y_offset, 1, '4.1.1', level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT đề nghị hoàn (Tài khoản 1331)',
                          level_2_style)
        sheet.write(y_offset, 10, '[42a]', level_2_style_center)
        sheet.write(y_offset, 11, 0, level_2_style_right)

        # line 38
        y_offset += 1
        sheet.write(y_offset, 1, '4.1.2', level_2_style_borderleft_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT đề nghị hoàn (Tài khoản 1332)',
                          level_2_style)
        sheet.write(y_offset, 10, '[42b]', level_2_style_center)
        sheet.write(y_offset, 11, 0, level_2_style_right)
        # line 39
        y_offset += 1
        sheet.write(y_offset, 1, 4.2, level_1_style_borderlefbottom_center)
        sheet.merge_range(y_offset, 2, y_offset, 9,
                          'Thuế GTGT còn được khấu trừ chuyển kỳ sau ([43] = [41] - [42])',
                          level_1_style_bottom)
        sheet.write(y_offset, 10, '[43]', level_2_style_bottom)
        sheet.write_formula(y_offset, 11, '=L35-L36', level_2_style_borderbottomright)
        # line 40
        y_offset += 1
        sheet.set_row(y_offset, 30)
        sheet.merge_range(y_offset, 1, y_offset, 11,
                          'NHÂN VIÊN ĐẠI LÝ THUẾ',
                          title_style_bold_left_black)
        # line 41
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2,
                          'Họ và tên', style_left_black)
        sheet.merge_range(y_offset, 3, y_offset, 6,
                          '',
                          full_border)
        sheet.write(y_offset, 9, 'Người ký', style_right_black)
        sheet.merge_range(y_offset, 10, y_offset, 11, self.env.user.name, full_border)
        # line 42
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2,
                          'Chứng chỉ hành nghề số', style_left_black)
        sheet.merge_range(y_offset, 3, y_offset, 6,
                          '',
                          full_border)
        sheet.write(y_offset, 9, 'Ngày ký', style_right_black)
        sheet.merge_range(y_offset, 10, y_offset, 11, datetime.today().strftime("%d/%m/%Y"), full_border)
        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file

    def _get_lines_by_grid(self, options, line_id, grids):
        if not self.env.context.get('print_mode', False) or not options.get('skip_base', False):
            return super()._get_lines_by_grid(options, line_id, grids)
        report = self.env['account.tax.report'].browse(options['tax_report'])
        formulas_dict = dict(
            report.line_ids.filtered(lambda l: l.code and l.formula).mapped(lambda l: (l.code, l.formula)))

        # Build the report, line by line
        lines = {}
        lines_mapping = {}
        deferred_total_lines = []
        for each_box in set(report.line_ids.mapped('vas_tax_field')):
            lines.update({each_box: 0})
        for current_line in report.get_lines_in_hierarchy():
            hierarchy_level = self._get_hierarchy_level(current_line)
            parent_line_id = lines_mapping[current_line.parent_id.id]['id'] if current_line.parent_id.id else None

            if current_line.formula:
                # Then it's a total line
                # We defer the adding of total lines, since their balance depends
                # on the rest of the report. We use a special dictionnary for that,
                # keeping track of hierarchy level
                line = self._prepare_total_line(current_line, parent_line_id, hierarchy_level)
                # Using len(lines) since the line is appended later
            elif current_line.tag_name:
                # Then it's a tax grid line
                line = self._build_tax_grid_line(grids[current_line.id][0], parent_line_id, hierarchy_level, options)
            else:
                # Then it's a title line
                line = self._build_tax_section_line(current_line, parent_line_id, hierarchy_level)
            lines_mapping[current_line.id] = line
            total_amount = lines.get(current_line.vas_tax_field, 0)
            if line.get('columns', 0):
                lines.update({current_line.vas_tax_field: total_amount + line.get('columns', 0)[0].get('balance')})
        return lines


    def _get_columns_name(self, options):
        if not self.env.context.get('print_mode', False) or not options.get('skip_base', False):
            return super()._get_columns_name(options)
        columns_header = []
        #title
        title_line = [{'name': 'TỜ KHAI THUẾ GIÁ TRỊ GIA TĂNG (01/GTGT) \n (Dành cho người nộp thuế khai thuế GTGT theo phương pháp khấu trừ) \nHoạt động sản xuất kinh doanh thông thường',
                        'class': 'char',
                       'style': 'white-space: pre; align:center, height: 100px',
                       'colspan': 11}]
        columns_header += title_line
        return columns_header


    def get_sql_detail_vas_report(self, options):
        sql = """
        select untax_balnce.*, tax.tax from (
            SELECT
                              -- account_tax_report_line_tags_rel.account_tax_report_line_id,
                   account_move.id,account_move.name as invocie_name,account_move.date, atg.name as percent_name,acc_tag.tax_group,parent_report_line.name as root_tax_name, max(account_move_line.name) as move_name, max(rp.name) as partner_name, max(rp.vat) as tax_code,
                               sum(COALESCE(account_move_line.balance, 0)
                                   * CASE WHEN acc_tag.tax_negate THEN -1 ELSE 1 END
                                   * CASE WHEN account_move_line.tax_tag_invert THEN -1 ELSE 1 END
                               ) AS untax_balance
                          FROM "account_move_line" LEFT JOIN "account_move" AS "account_move_line__move_id" ON ("account_move_line"."move_id" = "account_move_line__move_id"."id")
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
                        join account_tax_report_line parent_report_line
                                    on parent_report_line.id = split_part( report_line.parent_path, '/', 1)::int
                        join account_tax_group atg
                                    on atg.id = acc_tag.tax_group
                        left join res_partner rp
                                    on account_move_line.partner_id = rp.id
                         WHERE ((((((((("account_move_line"."display_type" not in ('line_section', 'line_note')) OR "account_move_line"."display_type" IS NULL) AND (("account_move_line__move_id"."state" != 'cancel') OR "account_move_line__move_id"."state" IS NULL))
                                         AND ("account_move_line"."company_id" in (1))) AND ("account_move_line"."date" <= '{date_to}')) AND ("account_move_line"."date" >= '{date_from}'))
                                      AND ("account_move_line__move_id"."state" = 'posted')) AND
                                 ("account_move_line__move_id"."fiscal_position_id" IS NULL  OR
                                  ("account_move_line__move_id"."fiscal_position_id" in (SELECT "account_fiscal_position".id FROM "account_fiscal_position" WHERE "account_fiscal_position"."foreign_vat" IS NULL  AND ("account_fiscal_position"."company_id" IS NULL  OR ("account_fiscal_position"."company_id" in ({company})))))))
                                    AND (("account_move_line__move_id"."always_tax_exigible" = True) OR
                                         (("account_move_line"."tax_line_id" IS NULL  AND ("account_move_line"."id" not in (SELECT "account_move_line_id" FROM "account_move_line_account_tax_rel" where "account_move_line_id" is not null)))
                                              OR ("account_move_line__move_id"."tax_cash_basis_rec_id" IS NOT NULL OR (("account_move_line"."tax_line_id" in (SELECT "account_tax".id FROM "account_tax" WHERE (("account_tax"."tax_exigibility" != 'on_payment')
                                                                                                                                                                                                    OR "account_tax"."tax_exigibility" IS NULL) AND ("account_tax"."company_id" IS NULL  OR ("account_tax"."company_id" in ({company})))))
                                                                                                                           OR ("account_move_line"."id" in (SELECT "account_move_line_id" FROM "account_move_line_account_tax_rel" WHERE "account_tax_id" IN (SELECT "account_tax".id FROM "account_tax" WHERE (("account_tax"."tax_exigibility" != 'on_payment') OR "account_tax"."tax_exigibility" IS NULL) AND ("account_tax"."company_id" IS NULL
                                                                                                                       OR ("account_tax"."company_id" in ({company}))))))))))) AND ("account_move_line"."company_id" IS NULL  OR ("account_move_line"."company_id" in ({company})))
                           AND report_line.report_id = {tax_report} and report_line.vas_tax_field in ('23', '27', '29','30', '32')
                           AND account_journal.id = account_move_line.journal_id
                         GROUP BY account_move.id,account_move.name, account_move.name,atg.name, acc_tag.tax_group,parent_report_line.name, report_line.vas_tax_field ) as untax_balnce
            
            left join
            (
            SELECT
                              -- account_tax_report_line_tags_rel.account_tax_report_line_id,
                   account_move.id,acc_tag.name,acc_tag.tax_group,
                               sum(COALESCE(account_move_line.balance, 0)
                                   * CASE WHEN acc_tag.tax_negate THEN -1 ELSE 1 END
                                   * CASE WHEN account_move_line.tax_tag_invert THEN -1 ELSE 1 END
                               ) AS tax
                          FROM "account_move_line" LEFT JOIN "account_move" AS "account_move_line__move_id" ON ("account_move_line"."move_id" = "account_move_line__move_id"."id")
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
                         WHERE ((((((((("account_move_line"."display_type" not in ('line_section', 'line_note')) OR "account_move_line"."display_type" IS NULL) AND (("account_move_line__move_id"."state" != 'cancel') OR "account_move_line__move_id"."state" IS NULL))
                                         AND ("account_move_line"."company_id" in (1))) AND ("account_move_line"."date" <= '{date_to}')) AND ("account_move_line"."date" >= '{date_from}'))
                                      AND ("account_move_line__move_id"."state" = 'posted')) AND
                                 ("account_move_line__move_id"."fiscal_position_id" IS NULL  OR
                                  ("account_move_line__move_id"."fiscal_position_id" in (SELECT "account_fiscal_position".id FROM "account_fiscal_position" WHERE "account_fiscal_position"."foreign_vat" IS NULL  AND ("account_fiscal_position"."company_id" IS NULL  OR ("account_fiscal_position"."company_id" in ({company})))))))
                                    AND (("account_move_line__move_id"."always_tax_exigible" = True) OR
                                         (("account_move_line"."tax_line_id" IS NULL  AND ("account_move_line"."id" not in (SELECT "account_move_line_id" FROM "account_move_line_account_tax_rel" where "account_move_line_id" is not null)))
                                              OR ("account_move_line__move_id"."tax_cash_basis_rec_id" IS NOT NULL OR (("account_move_line"."tax_line_id" in (SELECT "account_tax".id FROM "account_tax" WHERE (("account_tax"."tax_exigibility" != 'on_payment')
                                                                                                                                                                                                    OR "account_tax"."tax_exigibility" IS NULL) AND ("account_tax"."company_id" IS NULL  OR ("account_tax"."company_id" in ({company})))))
                                                                                                                           OR ("account_move_line"."id" in (SELECT "account_move_line_id" FROM "account_move_line_account_tax_rel" WHERE "account_tax_id" IN (SELECT "account_tax".id FROM "account_tax" WHERE (("account_tax"."tax_exigibility" != 'on_payment') OR "account_tax"."tax_exigibility" IS NULL) AND ("account_tax"."company_id" IS NULL
                                                                                                                                                                                                                       OR ("account_tax"."company_id" in ({company}))))))))))) AND ("account_move_line"."company_id" IS NULL  OR ("account_move_line"."company_id" in ({company})))
                           AND report_line.report_id = {tax_report} and report_line.vas_tax_field in ('24', '28', '31','33')
                           AND account_journal.id = account_move_line.journal_id
                         GROUP BY account_move.id,acc_tag.name, acc_tag.tax_group, report_line.vas_tax_field ) as tax
            
            on tax.id = untax_balnce.id and tax.tax_group = untax_balnce.tax_group
            order by untax_balnce.root_tax_name, untax_balnce.date,untax_balnce.percent_name""".format(tax_report=options['tax_report'],date_to=options['date'].get('date_to'),date_from=options['date'].get('date_from'), company=self.env.company.id)

        self.env.cr.execute(sql)
        return self.env.cr.dictfetchall()