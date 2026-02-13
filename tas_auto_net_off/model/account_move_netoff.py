# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz
from datetime import datetime
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class AccountMoveNetoff(models.Model):
    _name = 'account.move.netoff'

    start_date = fields.Date(string="Start date")
    end_date = fields.Date(string="End date")
    status = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], string="Status", default='draft')
    move_ids = fields.One2many('account.move', 'move_netoff_id', string="Journal entry")

    def build_sql(self, company_id, start_date, end_date, accounts, previous_closing_date):
        if len(accounts.ids) == 0:
            return []
        sql = """
        select groupby as partner_id, account_id as account_id, sum(debit ) as debit, sum( credit) as credit, sum( balance) as balance
        from (
        select account_move_line.partner_id as groupby, account_move_line.account_id,
               'sum' as key,
            sum( account_move_line.debit ) as debit,
            sum( account_move_line.credit)  as credit,
            sum( account_move_line.balance) as balance
        from "account_move_line"
        left join "account_move" as "account_move_line__move_id" on ("account_move_line"."move_id" = "account_move_line__move_id"."id")
        where (
            (
                (
                    (
                        (
                            (
                                (("account_move_line"."display_type" not in ('line_section','line_note')) or "account_move_line"."display_type" is null)
                                and (("account_move_line__move_id"."state" != 'cancel') or "account_move_line__move_id"."state" is null)
                            )
                            and ("account_move_line"."company_id" = %(company_id)s )
                        )
                        and ("account_move_line"."date" <= %(end_date)s) and ("account_move_line"."date" >= %(start_date)s)
                    )
                    and ("account_move_line__move_id"."state" = 'posted')
                ) and (
                    (
                        (("account_move_line"."credit" != 0.0) or ("account_move_line"."debit" != 0.0))
                        or ("account_move_line"."amount_currency" = 0.0)
                    ) or ("account_move_line"."ref" is null)
                )
            ) and "account_move_line"."account_id" in %(account_ids)s
        ) and ("account_move_line"."company_id" is null  or ("account_move_line"."company_id" = %(company_id)s ))
        group by account_move_line.partner_id,  account_move_line.account_id
        
        union all
        select account_move_line.partner_id as groupby, account_move_line.account_id,
               'initial_balance' as key,
            sum( account_move_line.debit ) as debit,
            sum( account_move_line.credit)  as credit,
            sum( account_move_line.balance) as balance
        from "account_move_line"
        left join "account_move" as "account_move_line__move_id" on ("account_move_line"."move_id" = "account_move_line__move_id"."id")
        where (
            (
                (
                    (
                        (
                            (
                                (("account_move_line"."display_type" not in ('line_section','line_note')) or "account_move_line"."display_type" is null)
                                and (("account_move_line__move_id"."state" != 'cancel') or "account_move_line__move_id"."state" is null)
                            )
                            and ("account_move_line"."company_id" = %(company_id)s )
                        )
                        and ("account_move_line"."date" <= %(previous_closing_date)s )
                        and (
                            ("account_move_line"."date" >= null)
                            or
                            (
                                "account_move_line"."account_id" in
                                (
                                    select "account_account".id from "account_account"
                                    where ("account_account"."user_type_id" in
                                    (
                                        select "account_account_type".id
                                        from "account_account_type"
                                        where ("account_account_type"."include_initial_balance" = true)
                                        order by  "account_account_type"."id"
                                    ))
                                    and ("account_account"."company_id" is null
                                    or ("account_account"."company_id" = %(company_id)s))
                                    order by  "account_account"."id"
                                )
                            )
                        )
                    )
                    and ("account_move_line__move_id"."state" = 'posted')
                ) and (
                    (
                        (("account_move_line"."credit" != 0.0) or ("account_move_line"."debit" != 0.0))
                        or ("account_move_line"."amount_currency" = 0.0)
                    ) or ("account_move_line"."ref" is null)
                )
            ) and "account_move_line"."account_id" in  %(account_ids)s
        ) and ("account_move_line"."company_id" is null  or ("account_move_line"."company_id" =  %(company_id)s))
        group by account_move_line.partner_id,  account_move_line.account_id) as partner_ledger
        group by partner_id, account_id

        """
        self.env.cr.execute(sql, {
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
            'account_ids': tuple(accounts.ids),
            'previous_closing_date': previous_closing_date,
        })
        _logger.info(self._cr.query.decode().lower())
        records = self.env.cr.fetchall()
        return records

    def do_transfer(self):

        company_id = self.env.company.id
        journal_netof = self.env['account.journal'].sudo().search([('code', '=', 'NetOf'),('company_id', '=', company_id)])
        bisexual_accounts = self.env['account.account'].search([('company_id', '=', company_id), ('bisexual_account', '=', True)])

        yesterday = (self.start_date - timedelta(days=1)).strftime('%Y-%m-%d')
        lines = self.build_sql(company_id, self.start_date.strftime('%Y-%m-%d'), self.end_date.strftime('%Y-%m-%d'), bisexual_accounts, yesterday )


        computed_accounts = {}

        for line in lines:
            if line[1] not in computed_accounts:
                computed_accounts[line[1]] = {
                    'positive': 0,
                    'negative': 0
                }

            if line[4] >= 0:
                computed_accounts[line[1]]['positive'] += line[4]
            else:
                computed_accounts[line[1]]['negative'] += line[4]

        line_ids = []
        for ac in computed_accounts:
            line = computed_accounts.get(ac)
            account_id = ac
            original_account = self.env['account.account'].browse(account_id)
            contra_account = self.env['account.account'].browse(account_id).contra_account

            if original_account.compute_base_on == 'du_ben_no' and line.get('positive') > 0:
                line_ids.append(
                    (0, 0, {
                        "account_id": account_id,
                        'credit': line.get('positive'),
                        'is_netoff': 1,
                        'ref': "Netoff " + str(original_account.code) + " sang " + contra_account.code,
                        'name': 'But toan netoff'
                    }))
                line_ids.append(
                    (0, 0, {
                        "account_id": contra_account.id,
                        'debit': line.get('positive'),
                        'is_netoff': 1,
                        'ref': "Netoff " + str(original_account.code) + " sang " + contra_account.code,
                        'name': 'But toan netoff'
                    }))

            if original_account.compute_base_on == 'du_ben_co' and line.get('negative') < 0:
                line_ids.append(
                    (0, 0, {
                        "account_id": account_id,
                        'debit': -line.get('negative'),
                        'is_netoff': 1,
                        'ref': "Netoff " + str(original_account.code) + " sang " + contra_account.code,
                        'name': 'But toan netoff'
                    }))
                line_ids.append(
                    (0, 0, {
                        "account_id": contra_account.id,
                        'credit': -line.get('negative'),
                        'is_netoff': 1,
                        'ref': "Netoff " + str(original_account.code) + " sang " + contra_account.code,
                        'name': 'But toan netoff'
                    }))

        if len(line_ids) <= 0:
            return

        move_vals = {
            'journal_id': journal_netof.id,
            'company_id': company_id,
            'currency_id': self.env.company.currency_id.id,
            'date': self.end_date,
            'line_ids': line_ids,
            'move_netoff_id': self.id
        }

        account_move = self.env['account.move'].create(move_vals)
        account_move.action_post()

        move_reversal = self.env['account.move.reversal'].with_context(active_model="account.move",
                                                                       active_ids=account_move.ids).create({
            'date': self.end_date + timedelta(days=1),
            'reason': 'reverse netoff entry',
            'refund_method': 'cancel',
        })
        reversal = move_reversal.reverse_moves()
        reverse_move = self.env['account.move'].browse(reversal['res_id'])
        reverse_move.action_post()