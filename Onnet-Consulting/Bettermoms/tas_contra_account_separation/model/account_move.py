# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz
from odoo.exceptions import ValidationError, UserError
import warnings
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    separation_ids = fields.One2many('account.move.line.separation', 'move_id', string='Đối ứng')
    is_separated = fields.Boolean(string='Đã được tách đối ứng', default=False)

    def separate_contra_account(self, force_separate=False, is_show_error=True):
        hasError = False
        message = ''
        for move in self:
            if not force_separate and move.state != 'posted':
                hasError = True
                message += _('Entry ' + str(move.name) + ' chưa được hạch toán \n')
                continue

            if not force_separate and move.is_separated:
                hasError = True
                message += _('Entry ' + str(move.name) + 'Đã được tách đối ứng \n')
                continue

            debit = {
                'accounts': []
            }
            credit = {
                'accounts': []
            }
            for entry_item in move.line_ids:
                value = {
                    'account_id': entry_item.account_id.id,
                    'amount': entry_item.debit if entry_item.debit > 0 else entry_item.credit if entry_item.credit > 0 else 0
                }
                if entry_item.debit > 0:
                    debit['accounts'].append(value)
                elif entry_item.credit > 0:
                    credit['accounts'].append(value)

            if len(debit.get('accounts')) > 1 and len(credit.get('accounts')) > 1:
                hasError = True
                message += _('Không thể tách bút toán đối ứng của Entry ' + str(move.name) + '\n')
                continue

#             thưc hiện tách đối ứng

            line_ids = []
            if len(debit.get('accounts')) == 1:
                for account in credit.get('accounts'):
                    line_ids.append((0, 0, {
                        'debit_account': debit.get('accounts')[0]['account_id'],
                        'credit_account': account['account_id'],
                        'amount': account['amount'],
                        'company_id': move.company_id.id,
                        'move_id': move.id
                    }))
            elif len(credit.get('accounts')) == 1:
                for account in debit.get('accounts'):
                    line_ids.append((0, 0, {
                        'debit_account': account['account_id'],
                        'credit_account': credit.get('accounts')[0]['account_id'],
                        'amount': account['amount'],
                        'company_id': move.company_id.id,
                        'move_id': move.id
                    }))

            if len(line_ids) > 0:
                move.update({
                    'separation_ids': line_ids,
                    'is_separated': True
                })
                self.env.cr.commit()

        if hasError and is_show_error:
            raise UserError(message)

    def task_separate_counterpart_account(self):
        try:
            # account_moves = self.env['account.move'].sudo().search([('is_separated', '=', False), ('company_id', '=', 7)], limit=1000)
            account_moves = self.env['account.move'].sudo().search([('is_separated', '=', False)], limit=5000, order='invoice_date desc')
            account_moves.separate_contra_account(True)
        except Exception as e:
            info = "Không thể tách đối ứng " + e.args[0]
            _logger.info(info)

    # def action_post(self):
    #     res = super(AccountMove, self).action_post()
    #     return res

    def _post(self, soft=True):
        posted = super(AccountMove, self)._post(soft=soft)
        self.separate_contra_account(True, False)
        return posted

    def button_draft(self):
        super(AccountMove, self).button_draft()
        self.update({
            'separation_ids': [(5, 0, 0)],
            'is_separated': False
        })


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    countered_accounts = fields.Char(compute="_compute_countered_accounts", string='Tk đối ứng', store=True)

    @api.depends('move_id.separation_ids')
    def _compute_countered_accounts(self):
        # NOTE: this field cannot be stored as the line_id is usually removed
        # through cascade deletion, which means the compute would be false
        for line in self:
            contra_account = ''
            separate = ''
            for countered_account in line.move_id.separation_ids:
                if countered_account.debit_account.id == line.account_id.id and line.debit != 0:
                    if countered_account.credit_account.code not in contra_account:
                        contra_account += separate + countered_account.credit_account.code
                        separate = ', '
                elif countered_account.credit_account.id == line.account_id.id and line.credit != 0:
                    if countered_account.debit_account.code not in contra_account:
                        contra_account += separate + countered_account.debit_account.code
                        separate = ', '
            line.countered_accounts = contra_account


class AccountMoveTransfer(models.Model):
    _name = 'account.move.line.separation'

    debit_account = fields.Many2one('account.account', string="Tài khoản nợ")
    credit_account = fields.Many2one('account.account', string="Tài khoản có")
    amount = fields.Monetary(string='Số tiền')
    move_id = fields.Many2one('account.move', string="Entry")
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Account Currency',
                                  help="Forces all moves for this account to have this account currency.")
    company_branch = fields.Many2one("company.branch", string="Company Branch", related='move_id.company_branch_id')
    company_branch_vat = fields.Many2one("company.branch", string="Company Branch Vat", related='move_id.company_branch_vat')
