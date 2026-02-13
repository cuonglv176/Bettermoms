# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz


class AccountMoveTransfer(models.Model):
    _name = 'account.move.transfer'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    status = fields.Selection([
        ('draft', 'Draft'),
        ('transferred', 'Transferred')
    ], string="Status", default='draft')
    move_ids = fields.One2many('account.move', 'move_transfer_id', string="Journal entry")

    def do_transfer(self, original_accounts, destination_account, journal):
        company_id = self.env.company.id
        account_dict = {}
        for account in original_accounts:
            account_dict[account.id] = {
                'code': account.code,
                'debit': 0.0,
                'credit': 0.0
            }

        # transfer to account 911
        move_lines = self.env['account.move.line'].search(
            [('date', '>=', self.start_date),
             ('date', '<=', self.end_date),
             ('display_type', 'not in', ('line_section', 'line_note')),
             ('parent_state', '=', 'posted'),
             ('company_id', '=', company_id)])
        for move_line in move_lines:
            if account_dict.get(move_line.account_id.id):
                account_dict[move_line.account_id.id]['debit'] += move_line.debit
                account_dict[move_line.account_id.id]['credit'] += move_line.credit

        line_ids = []
        total_911_debit = 0.0
        total_911_credit = 0.0
        for account_index in account_dict:
            account = account_dict.get(account_index)
            dif = account.get('debit') - account.get('credit')

            if dif > 0:
                total_911_debit += dif
                line_ids.append(
                    (0, 0, {
                        "account_id": account_index,
                        'credit': dif,
                        'is_transfer': 1,
                        'ref': "KC " + str(account.get('code')) + " sang " + destination_account.code,
                        'name': 'But toan ket chuyen'
                    })
                )
                line_ids.append(
                    (0, 0, {
                        "account_id": destination_account.id,
                        'debit': dif,
                        'is_transfer': 1,
                        'ref': "KC " + str(str(account.get('code'))) + " sang " + destination_account.code,
                        'name': 'But toan ket chuyen'
                    },))
            elif dif < 0:
                total_911_credit += -dif
                line_ids.append(
                    (0, 0, {
                        "account_id": account_index,
                        'debit': -dif,
                        'is_transfer': 1,
                        'ref': "KC " + str(account.get('code')) + " sang " + destination_account.code,
                        'name': 'But toan ket chuyen'
                    }))
                line_ids.append(
                    (0, 0, {
                        "account_id": destination_account.id,
                        'credit': -dif,
                        'is_transfer': 1,
                        'ref': "KC " + str(account.get('code')) + " sang " + destination_account.code,
                        'name': 'But toan ket chuyen'
                    }))

        if len(line_ids) == 0:
            return

        move_vals = {
            'journal_id': journal.id,
            'company_id': company_id,
            'currency_id': self.env.company.currency_id.id,
            'date': self.end_date,
            'line_ids': line_ids,
            'move_transfer_id': self.id
        }
        account_move = self.env['account.move'].create(move_vals)
        account_move.action_post()

    def transfer(self):
        company_id = self.env.company.id

        account_911 = self.env['account.account'].sudo().search([('level', '=', 3),
                                                             ('type', '=', 'chitiet'),
                                                             ('code', '=', '91110001'),
                                                             ('company_id', '=', company_id)
                                                            ])

        account_154 = self.env['account.account'].sudo().search([('level', '=', 3),
                                                                 ('type', '=', 'chitiet'),
                                                                 ('code', '=', '15410001'),
                                                                 ('company_id', '=', company_id)
                                                                 ])
        account_632 = self.env['account.account'].sudo().search([('level', '=', 3),
                                                                 ('type', '=', 'chitiet'),
                                                                 ('code', '=', '63230001'),
                                                                 ('company_id', '=', company_id)
                                                                 ])
        account_4212 = self.env['account.account'].sudo().search([('level', '=', 3),
                                                                  ('type', '=', 'chitiet'),
                                                                  ('code', '=', '42120001'),
                                                                  ('company_id', '=', company_id)
                                                                  ])
        journal1 = self.env['account.journal'].sudo().search([('code', '=', 'KCCK1'),
                                                             ('company_id', '=', company_id)
                                                             ])
        journal2 = self.env['account.journal'].sudo().search([('code', '=', 'KCCK2'),
                                                             ('company_id', '=', company_id)
                                                             ])
        journal3 = self.env['account.journal'].sudo().search([('code', '=', 'KCCK3'),
                                                             ('company_id', '=', company_id)
                                                             ])
        journal4 = self.env['account.journal'].sudo().search([('code', '=', 'KCCK4'),
                                                             ('company_id', '=', company_id)
                                                             ])
        # ket chuyen 621, 622, 627 sang 154
        accounts = self.env['account.account'].sudo().search([
            ('company_id', '=', company_id),
            ('level', '=', 3),
            ('type', '=', 'chitiet'),
            '|', '|',
            ('code', '=ilike', '621%'),
            ('code', '=ilike', '622%'),
            ('code', '=ilike', '627%')
        ])
        self.do_transfer(accounts, account_154, journal1)

        # ket chuyen 154 sang 632
        self.do_transfer(account_154, account_632, journal2)

        # ket chuyen 5x, 6x, 7x, 8x qua 911
        accounts = self.env['account.account'].sudo().search([
            ('company_id', '=', company_id),
            ('level', '=', 3),
            ('type', '=', 'chitiet'),
            '|', '|', '|', '|', '|', '|', '|', '|',
            ('code', '=ilike', '51%'),
            ('code', '=ilike', '52%'),
            ('code', '=ilike', '61%'),
            ('code', '=ilike', '623%'),
            ('code', '=ilike', '63%'),
            ('code', '=ilike', '64%'),
            ('code', '=ilike', '71%'),
            ('code', '=ilike', '81%'),
            ('code', '=ilike', '82%')
        ])
        self.do_transfer(accounts, account_911, journal3)

        # ket chuyen 911 sang 4212
        self.do_transfer(account_911, account_4212, journal4)
        self.status = 'transferred'