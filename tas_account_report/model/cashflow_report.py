# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz
from datetime import datetime, timedelta


class AccountCashFlowReport(models.AbstractModel):
    _inherit = 'account.cash.flow.report'

    def get_tax_data(self, start_date, end_date, items, accounts):
        lines = self.env['account.move.line'].sudo().search(
            [('company_id', '=', self.env.company.id),
             ('account_id.level', '=', '3'),
             ('parent_state', '=', 'posted'),
             ('move_id.journal_id.type', 'in', ['cash', 'bank']),
             # ('account_id.user_type_id.name', '=', 'Bank and Cash'),
             # ('account_id.parent_id.id', 'in', accounts.ids),
             ('date', '>=', start_date),
             ('date', '<=', end_date)
             ])

        for line in lines:
            # 20210826 epsilo account 22421 có 5 kí tự
            # account_code = line.account_id.code[:4]
            account_code = line.account_id.code
            if items.get(account_code):
                for item in items.get(account_code):
                    if 'debit' in items.get(account_code).get(item):
                        items.get(account_code).get(item)['debit'] += line.debit
                    if 'credit' in items.get(account_code).get(item):
                        items.get(account_code).get(item)['credit'] += line.credit

        out = {
            '01': {
                'name': 'Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác',
                'value': 0
            },
            '02': {
                'name': 'Tiền chi trả cho người cung cấp hàng hóa và dịch vụ',
                'value': 0
            },
            '03': {
                'name': 'Tiền chi trả cho người lao động',
                'value': 0
            },
            '04': {
                'name': 'Tiền chi trả lãi vay',
                'value': 0
            },
            '05': {
                'name': 'Tiền thuế thu nhập doanh nghiệp đã nộp',
                'value': 0
            },
            '06': {
                'name': 'Tiền thu khác từ hoạt động kinh doanh',
                'value': 0
            },
            '07': {
                'name': 'Tiền chi khác cho hoạt động kinh doanh',
                'value': 0
            },
            '20': {
                'name': 'Lưu chuyển tiền thuần từ hoạt động kinh doanh',
                'value': 0
            },
            '21': {
                'name': 'Tiền chi để mua sắm, xây dựng tài sản cố định và các tài sản dài hạn khác',
                'value': 0
            },
            '22': {
                'name': 'Tiền thu từ thanh lý, nhượng bán tài sản cố định và các tài sản dài hạn khác',
                'value': 0
            },
            '23': {
                'name': 'Tiền chi cho vay, mua các công cụ nợ của đơn vị khác',
                'value': 0
            },
            '24': {
                'name': 'Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác',
                'value': 0
            },
            '25': {
                'name': 'Tiền chi đầu tư góp vốn vào đơn vị khác',
                'value': 0
            },
            '26': {
                'name': 'Tiền thu hồi đầu tư góp vốn vào đơn vị khác',
                'value': 0
            },
            '27': {
                'name': 'Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia',
                'value': 0
            },
            '30': {
                'name': 'Lưu chuyển tiền thuần từ hoạt động đầu tư',
                'value': 0
            },
            '31': {
                'name': 'Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu',
                'value': 0
            },
            '32': {
                'name': 'Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành',
                'value': 0
            },
            '33': {
                'name': 'Tiền thu từ đi vay ',
                'value': 0
            },
            '34': {
                'name': 'Tiền trả nợ gốc vay',
                'value': 0
            },
            '35': {
                'name': 'Tiền trả nợ gốc thuê tài chính',
                'value': 0
            },
            '36': {
                'name': 'Cổ tức, lợi nhuận đã trả cho chủ sở hữu',
                'value': 0
            },
            '40': {
                'name': 'Lưu chuyển tiền thuần từ hoạt động tài chính',
                'value': 0
            },
            '50': {
                'name': 'Lưu chuyển tiền thuần trong kỳ',
                'value': 0
            },
            '60': {
                'name': 'Tiền và tương đương tiền đầu kỳ',
                'value': 0
            },
            '61': {
                'name': 'Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ',
                'value': 0
            },
            '70': {
                'name': 'Tiền và tương đương tiền cuối kỳ',
                'value': 0
            }
        }

        for account_item in items:
            account = items.get(account_item)
            for item in account:
                out[item]['value'] += (account[item]['credit'] if 'credit' in account[item] else 0) - (account[item]['debit'] if 'debit' in account[item] else 0)

        out['20']['value'] = out['01']['value'] + out['02']['value'] + out['03']['value'] + out['04']['value'] + \
                             out['05']['value'] + out['06']['value'] + out['07']['value']
        out['30']['value'] = out['21']['value'] + out['22']['value'] + out['23']['value'] + out['24']['value'] + \
                             out['25']['value']
        out['40']['value'] = out['31']['value'] + out['32']['value'] + out['33']['value'] + out['34']['value'] + \
                             out['35']['value']
        out['50']['value'] = out['30']['value'] + out['40']['value'] + out['20']['value']
        out['70']['value'] = out['50']['value'] + out['60']['value'] + out['61']['value']
        return out

    def create_sheet(self, workbook, sheet_name, date_from, date_to, options):
        header_style = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter',
             'bg_color': '#BE1622', 'font_color': 'white', 'border': 1})
        header_style_1 = workbook.add_format(
            {'font_name': 'Times New Roman', 'font_size': 10, 'bold': True, 'valign': 'vcenter', 'border': 1,
             'bg_color': 'yellow'})
        title_style = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'align': 'center'})
        title_style_left = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'align': 'left'})
        title_style_right = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'align': 'right'})
        item_style = workbook.add_format(
            {'font_name': 'Times New Roman', 'align': 'left'})
        item_style_center = workbook.add_format(
            {'font_name': 'Times New Roman', 'align': 'center'})
        item_style_right = workbook.add_format(
            {'font_name': 'Times New Roman', 'align': 'right'})

        title_style_footer = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True})
        title_style_footer_2 = workbook.add_format(
            {'font_name': 'Times New Roman', 'bold': True, 'align': 'center'})
        title_style_footer_3 = workbook.add_format(
            {'font_name': 'Times New Roman', 'align': 'center'})

        sheet_sale = workbook.add_worksheet(sheet_name)
        sheet_sale.set_column('A:A', 60)
        sheet_sale.set_column('B:B', 7)
        sheet_sale.set_column('C:C', 20)
        sheet_sale.set_column('D:D', 25)
        sheet_sale.set_column('K:K', 20)
        sheet_sale.set_column('L:L', 15)
        sheet_sale.set_column('F:F', 15)
        sheet_sale.set_column('I:I', 15)
        sheet_sale.set_column('J:J', 15)
        sheet_sale.set_column('H:H', 15)
        sheet_sale.set_column('E:E', 15)

        sheet_sale.write(1, 0, 'BÁO CÁO LƯU CHUYỂN TIỀN TỆ', title_style_left)
        sheet_sale.write(1, 3, '(Theo phương pháp trực tiếp)', item_style)
        sheet_sale.write(2, 0, 'Cho năm tài chính từ ngày ' + date_from + ' đến ngày ' + date_to, item_style)
        sheet_sale.write(2, 3, 'Đơn vị tính: VND', item_style)

        sheet_sale.write(3, 0, 'CHỈ TIÊU', title_style_left)
        sheet_sale.write(3, 1, 'MÃ SỐ', title_style)
        sheet_sale.write(3, 2, 'THUYẾT MINH', title_style)
        sheet_sale.write(3, 3, 'KỲ NÀY', title_style_right)
        # sheet_sale.write(3, 4, 'KỲ TRƯỚC', title_style_right)

        # demo data
        items = {
            '1311': {
                '01': {
                    'credit': 0,
                    'debit': 0
                },
            },
            '3311': {
                '02': {
                    'credit': 0,
                    'debit': 0
                },
            },
            '3388': {
                '06': {
                    'credit': 0
                },
                '07': {
                    'debit': 0
                },
            },
            '3331': {
                '06': {
                    'credit': 0
                },
                '07': {
                    'debit': 0
                },
            },
            '3387': {
                '01': {
                    'credit': 0,
                    'debit': 0
                },
            },
            '6418': {
                '02': {
                    'credit': 0,
                    'debit': 0
                },
            },
        }
        # initialize items
        items = {}
        accounts = self.env['account.account'].sudo().search([('company_id', '=', self.env.company.id), '|',
                                                            ('cashflow_credit', 'not in', [False, '']),
                                                            ('cashflow_debit', 'not in', [False, '']),
                                                            ])
        for account in accounts:
            items[account.code] = {
            }
            if account.cashflow_credit:
                items[account.code] = {
                    account.cashflow_credit: {
                        'credit': 0
                    }
                }
            if account.cashflow_debit:
                if account.cashflow_debit == account.cashflow_credit:
                    items[account.code][account.cashflow_debit]['debit'] = 0
                else:
                    items[account.code][account.cashflow_debit] = {
                        'debit': 0
                    }

        # end initialize items
        def print_line_data(r, code, title=None):
            if title:
                sheet_sale.write(r, 0, title, title_style_left)
            sheet_sale.write(r+1, 0, lines.get(code).get('name'), item_style)
            sheet_sale.write(r+1, 1, code, item_style_center)
            sheet_sale.write(r+1, 3, lines.get(code).get('value'), item_style_right)
            # sheet_sale.write(r+1, 4, previous_lines.get(code).get('value'), item_style_right)

        tz = pytz.timezone(self.env.user.tz) or pytz.timezone('Asia/Ho_Chi_Minh')
        start = (pytz.utc.localize(fields.Datetime.from_string(date_from)).astimezone(tz))
        end = (pytz.utc.localize(fields.Datetime.from_string(date_to)).astimezone(tz))

        lines = self.get_tax_data(start, end, items, accounts)

        # compute Cash and cash equivalents, beginning of period
        payment_move_ids, payment_account_ids = self._get_liquidity_move_ids(options)
        beginning_period_options = self._get_options_beginning_period(options)
        currency_table_query = self.env['res.currency']._get_query_currency_table(options)
        for account_id, account_code, account_name, balance in self._compute_liquidity_balance(beginning_period_options,
                                                                                               currency_table_query,
                                                                                               payment_account_ids):
            lines['60']['value'] += balance
        lines['70']['value'] = lines['50']['value'] + lines['60']['value'] + lines['61']['value']

        row = 4
        print_line_data(row, '01', 'Lưu chuyển tiền từ hoạt động kinh doanh')
        row += 1
        print_line_data(row, '02')
        row += 1
        print_line_data(row, '03')
        row += 1
        print_line_data(row, '04')
        row += 1
        print_line_data(row, '05')
        row += 1
        print_line_data(row, '06')
        row += 1
        print_line_data(row, '07')
        row += 1
        print_line_data(row, '20')
        row += 2
        print_line_data(row, '21', 'Lưu chuyển tiền từ hoạt động đầu tư')
        row += 1
        print_line_data(row, '22')
        row += 1
        print_line_data(row, '23')
        row += 1
        print_line_data(row, '24')
        row += 1
        print_line_data(row, '25')
        row += 1
        print_line_data(row, '26')
        row += 1
        print_line_data(row, '27')
        row += 1
        print_line_data(row, '30')
        row += 2
        print_line_data(row, '31', 'Lưu chuyển tiền từ hoạt động tài chính')
        row += 1
        print_line_data(row, '32')
        row += 1
        print_line_data(row, '33')
        row += 1
        print_line_data(row, '34')
        row += 1
        print_line_data(row, '35')
        row += 1
        print_line_data(row, '36')
        row += 1
        print_line_data(row, '40')
        row += 1
        print_line_data(row, '50')
        row += 1
        print_line_data(row, '60')
        row += 1
        print_line_data(row, '61')
        row += 1
        print_line_data(row, '70')

        row += 6
        sheet_sale.write(row, 3, datetime.now().strftime(", Ngày %d tháng %m năm %Y"), item_style_center)
        row += 1
        sheet_sale.write(row, 0, 'Người lập biểu', title_style)
        sheet_sale.write(row, 1, 'Kế toán trưởng', title_style_left)
        sheet_sale.write(row, 3, 'Giám đốc', title_style)

    def get_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ctx = self._set_context(options)
        ctx.update({'no_format': True, 'print_mode': True, 'prefetch_fields': False})
        self.create_sheet(workbook, 'Cashflow', ctx['date_from'], ctx['date_to'], options)
        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file