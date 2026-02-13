# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.tools.misc import format_date, DEFAULT_SERVER_DATE_FORMAT
from datetime import timedelta, datetime
import io
import xlsxwriter

class AccountFCTcITGlReport(models.AbstractModel):
    _inherit = "account.general.ledger"
    _description = "General Ledger Report"
    _name = "account.fctcit.report"

    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_all_entries = False
    filter_journals = True
    filter_analytic = True
    filter_unfold_all = False

    @api.model
    def _get_templates(self):
        templates = super(AccountFCTcITGlReport, self)._get_templates()
        templates['line_template'] = 'ntp_fct_cit_report.line_fct_template'
        return templates

    @api.model
    def _get_columns_name(self, options):
        columns_names = [
            {'name': _('Detail')},
            {'name': _('Code')},
            {'name': _('Business Name')},
            {'name': _('Reference No.')},
            {'name': _('Partner')},
            {'name': _('Revenue'), 'class': 'number'},
            {'name': _('Date'), 'class': 'date'},
            {'name': _('Currency'), 'class': 'number'},
            {'name': _('Revenue to calculate VAT'), 'class': 'number'},
            {'name': _('Rate'), 'class': 'number'},
            {'name': _('VAT'), 'class': 'number'},
            {'name': _('Revenue to calculate CIT'), 'class': 'number'},
            {'name': _('Rate'), 'class': 'number'},
            {'name': _('CIT'), 'class': 'number'},
            {'name': _('Total FCT'), 'class': 'number'},
        ]
        return columns_names

    @api.model
    def _get_report_name(self):
        return _("FCT Report")

    def view_all_journal_items(self, options, params):
        if params.get('id'):
            params['id'] = int(params.get('id').split('_')[1])
        return self.env['account.report'].open_journal_items(options, params)

    ####################################################
    # MAIN METHODS
    ####################################################

    @api.model
    def _get_lines(self, options, line_id=None):
        offset = int(options.get('lines_offset', 0))
        remaining = int(options.get('lines_remaining', 0))
        balance_progress = float(options.get('lines_progress', 0))

        if offset > 0:
            # Case a line is expanded using the load more.
            return self._load_more_lines(options, line_id, offset, remaining, balance_progress)
        else:
            # Case the whole report is loaded or a line is expanded for the first time.
            return self._get_general_ledger_lines(options, line_id=line_id)

    @api.model
    def _get_general_ledger_lines(self, options, line_id=None):
        ''' Get lines for the whole report or for a specific line.
        :param options: The report options.
        :return:        A list of lines, each one represented by a dictionary.
        '''
        lines = []
        aml_lines = []
        options_list = self._get_options_periods_list(options)
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])
        date_from = fields.Date.from_string(options['date']['date_from'])
        company_currency = self.env.company.currency_id

        account_id = self.env['account.account'].search([('code', '=', 33383)])
        if account_id:
            expanded_account = account_id

        accounts_results = self._do_query(options_list, expanded_account=expanded_account)

        total_fct_revenue = total_cit_revenue = total_balance = total_fct = total_cit = 0.0
        for results in accounts_results:
            # No comparison allowed in the General Ledger. Then, take only the first period.
            # account.account record line.
            account_sum = results.get('revenue', {})

            # Check if there is sub-lines for the current period.

            # amount_currency = account_sum.get('amount_currency', 0.0) + account_un_earn.get('amount_currency', 0.0)
            total_fct += results.get('fct_vat', 0.0) or 0
            total_cit += results.get('cit_vat', 0.0) or 0
            fct_revenue = results.get('fct_revenue', 0.0) or 0
            cit_revenue = results.get('cit_revenue', 0.0) or 0
            balance = results.get('revenue', 0.0) or 0

            # lines.append(self._get_account_title_line(options, account, amount_currency, debit, credit, balance, has_lines))

            total_fct_revenue += fct_revenue
            total_cit_revenue += cit_revenue
            total_balance += balance
            lines.append(self._get_aml_line(options, results))

        if not line_id:
            # Report total line.
            lines.append(self._get_total_line(
                total_fct,
                total_cit,
                total_fct_revenue,
                total_cit_revenue,
                company_currency.round(total_balance),
            ))


        if self.env.context.get('aml_only'):
            return aml_lines
        return lines

    @api.model
    def _load_more_lines(self, options, line_id, offset, load_more_remaining, balance_progress):
        ''' Get lines for an expanded line using the load more.
        :param options: The report options.
        :param line_id: string representing the line to expand formed as 'loadmore_<ID>'
        :params offset, load_more_remaining: integers. Parameters that will be used to fetch the next aml slice
        :param balance_progress: float used to carry on with the cumulative balance of the account.move.line
        :return:        A list of lines, each one represented by a dictionary.
        '''
        lines = []
        expanded_account = self.env['account.account'].browse(int(line_id[9:]))

        load_more_counter = self.MAX_LINES

        # Fetch the next batch of lines.
        amls_query, amls_params = self._get_query_amls(options, expanded_account, offset=offset, limit=load_more_counter)
        self.env.cr.execute(amls_query, amls_params)
        for aml in self._cr.dictfetchall():
            # Don't show more line than load_more_counter.
            if load_more_counter == 0:
                break

            balance_progress += aml['balance']

            # account.move.line record line.
            lines.append(self._get_aml_line(options, expanded_account, aml, balance_progress))

            offset += 1
            load_more_remaining -= 1
            load_more_counter -= 1

        if load_more_remaining > 0:
            # Load more line.
            lines.append(self._get_load_more_line(
                options, expanded_account,
                offset,
                load_more_remaining,
                balance_progress,
            ))
        return lines

    ####################################################
    # OPTIONS
    ####################################################

    @api.model
    def _force_strict_range(self, options):
        ''' Duplicate options with the 'strict_range' enabled on the filter_date.
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options['date'] = new_options['date'].copy()
        new_options['date']['strict_range'] = True
        return new_options

    @api.model
    def _get_options_domain(self, options):
        # OVERRIDE
        domain = super()._get_options_domain(options)
        if options.get('no_search_account', False):
            return domain
        # Filter accounts based on the search bar.
        account_id = self.env['account.account'].search([('code', '=', 33383)])
        if account_id:
            domain += [('account_id', '=', account_id.id)]
        return domain

    @api.model
    def _get_options_sum_balance(self, options):
        ''' Create options used to compute the aggregated sums on accounts.
        The resulting dates domain will be:
        [
            ('date' <= options['date_to']),
            '|',
            ('date' >= fiscalyear['date_from']),
            ('account_id.user_type_id.include_initial_balance', '=', True)
        ]
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        fiscalyear_dates = self.env.company.compute_fiscalyear_dates(fields.Date.from_string(new_options['date']['date_from']))
        new_options['date'] = {
            'mode': 'range',
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
        }
        return new_options

    @api.model
    def _get_options_unaffected_earnings(self, options):
        ''' Create options used to compute the unaffected earnings.
        The unaffected earnings are the amount of benefits/loss that have not been allocated to
        another account in the previous fiscal years.
        The resulting dates domain will be:
        [
          ('date' <= fiscalyear['date_from'] - 1),
          ('account_id.user_type_id.include_initial_balance', '=', False),
        ]
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        new_options.pop('filter_accounts', None)
        fiscalyear_dates = self.env.company.compute_fiscalyear_dates(fields.Date.from_string(options['date']['date_from']))
        new_date_to = fiscalyear_dates['date_from'] - timedelta(days=1)
        new_options['date'] = {
            'mode': 'single',
            'date_to': new_date_to.strftime(DEFAULT_SERVER_DATE_FORMAT),
        }
        return new_options

    @api.model
    def _get_options_initial_balance(self, options):
        ''' Create options used to compute the initial balances.
        The initial balances depict the current balance of the accounts at the beginning of
        the selected period in the report.
        The resulting dates domain will be:
        [
            ('date' <= options['date_from'] - 1),
            '|',
            ('date' >= fiscalyear['date_from']),
            ('account_id.user_type_id.include_initial_balance', '=', True)
        ]
        :param options: The report options.
        :return:        A copy of the options.
        '''
        new_options = options.copy()
        fiscalyear_dates = self.env.company.compute_fiscalyear_dates(fields.Date.from_string(options['date']['date_from']))
        new_date_to = fields.Date.from_string(new_options['date']['date_from']) - timedelta(days=1)
        new_options['date'] = {
            'mode': 'range',
            'date_from': fiscalyear_dates['date_from'].strftime(DEFAULT_SERVER_DATE_FORMAT),
            'date_to': new_date_to.strftime(DEFAULT_SERVER_DATE_FORMAT),
        }
        return new_options

    ####################################################
    # QUERIES
    ####################################################

    @api.model
    def _get_query_sums(self, options_list, expanded_account=None):
        ''' Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all accounts.
        - sums for the initial balances.
        - sums for the unaffected earnings.
        - sums for the tax declaration.
        :param options_list:        The report options list, first one being the current dates range, others being the
                                    comparisons.
        :param expanded_account:    An optional account.account record that must be specified when expanding a line
                                    with of without the load more.
        :return:                    (query, params)
        '''
        options = options_list[0]
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        params = []
        queries = []

        # Create the currency table.
        # As the currency table is the same whatever the comparisons, create it only once.
        ct_query = self.env['res.currency']._get_query_currency_table(options)

        # ============================================
        # 1) Get sums for all accounts.
        # ============================================

        domain = [('account_id', '=', expanded_account.id)] if expanded_account else []

        for i, options_period in enumerate(options_list):

            # The period domain is expressed as:
            # [
            #   ('date' <= options['date_to']),
            #   '|',
            #   ('date' >= fiscalyear['date_from']),
            #   ('account_id.user_type_id.include_initial_balance', '=', True),
            # ]

            new_options = self._get_options_sum_balance(options_period)
            new_options.get('date').update(strict_range=True)
            new_options.update(no_search_account=True)
            tables, first_where_clause, where_params = self._query_get(new_options, domain=[])
            params += where_params
            params += [expanded_account.id]
            new_options.update(no_search_account=False)
            tables, where_clause, where_params = self._query_get(new_options, domain=domain)
            params += where_params
            params += where_params
            queries.append('''
               select general.*, (general.revenue + cit.cit_vat) as cit_revenue, cit.cit_vat as cit_vat,
                   (general.revenue + coalesce(fct.fct_vat,0) + coalesce(cit.cit_vat,0)) as fct_revenue, fct.fct_vat as fct_vat, general.cit_vat as cit_perc, general.fct_vat as fct_perc , general.amount_currency ,
                   general.currency_id from (
                     (SELECT account_move_line.move_id as id, abs(account_move_line.balance) as revenue, rp.name as partner_name, fbl.code AS name,
                     fbl.name as business_name,account_move.ref as ref, account_move_line.date, aa.cit_vat , aa.fct_vat, account_move_line.amount_currency, account_move_line.currency_id
                           FROM "account_move_line" 
                                    LEFT JOIN "account_move" AS "account_move_line__move_id" ON ("account_move_line"."move_id" = "account_move_line__move_id"."id")
                                    JOIN account_move
                                         ON account_move_line.move_id = account_move.id
                                    JOIN account_journal
                                         ON account_move.journal_id = account_journal.id
                                    join account_account aa
                                            on aa.id = account_move_line.account_id
                                    join res_partner rp 
                                            on rp.id = account_move_line.partner_id
                                            
                                    join product_product pp
                                        on account_move_line.product_id = pp.id
                                    join product_template pt
                                                on pp.product_tmpl_id = pt.id
                                    left join fct_business_line fbl
                                                on fbl.id = pt.fct_business 
                           WHERE %s
            ) general left join
                (SELECT account_move.id, abs(account_move_line.balance) as fct_vat
                           FROM "account_move_line" 
                                    LEFT JOIN "account_move" AS "account_move_line__move_id" ON ("account_move_line"."move_id" = "account_move_line__move_id"."id")
                                    JOIN account_move
                                         ON account_move_line.move_id = account_move.id
                                    left JOIN account_account_tag_account_move_line_rel aml_tag
                                              ON aml_tag.account_move_line_id = account_move_line.id
                                    JOIN account_journal
                                         ON account_move.journal_id = account_journal.id
                                    left JOIN account_account_tag acc_tag
                                              ON aml_tag.account_account_tag_id = acc_tag.id
                           WHERE %s
                          ) fct on fct.id = general.id
                    left join (
                        SELECT account_move.id, abs(account_move_line.balance) as cit_vat
                           FROM "account_move_line" 
                                    LEFT JOIN "account_move" AS "account_move_line__move_id" ON ("account_move_line"."move_id" = "account_move_line__move_id"."id")
                                    JOIN account_move
                                         ON account_move_line.move_id = account_move.id
                                    left JOIN account_account_tag_account_move_line_rel aml_tag
                                              ON aml_tag.account_move_line_id = account_move_line.id
                                    JOIN account_journal
                                         ON account_move.journal_id = account_journal.id
                                    left JOIN account_account_tag acc_tag
                                              ON aml_tag.account_account_tag_id = acc_tag.id
                           WHERE %s
            
                ) cit on cit.id = general.id) order by general.date desc 
            ''' % (first_where_clause + ' and account_move_line.product_id is not null AND account_move_line.move_id in (select move_id from account_move_line where account_id = %s)',
                   where_clause + " and acc_tag.tax_type = 'fct_vat'",
                   where_clause + "and acc_tag.tax_type = 'fct_cit'"))


        return ' '.join(queries), params

    @api.model
    def _do_query(self, options_list, expanded_account=None, fetch_lines=True):
        ''' Execute the queries, perform all the computation and return (accounts_results, taxes_results). Both are
        lists of tuple (record, fetched_values) sorted by the table's model _order:
        - accounts_values: [(record, values), ...] where
            - record is an account.account record.
            - values is a list of dictionaries, one per period containing:
                - sum:                              {'debit': float, 'credit': float, 'balance': float}
                - (optional) initial_balance:       {'debit': float, 'credit': float, 'balance': float}
                - (optional) unaffected_earnings:   {'debit': float, 'credit': float, 'balance': float}
                - (optional) lines:                 [line_vals_1, line_vals_2, ...]
        - taxes_results: [(record, values), ...] where
            - record is an account.tax record.
            - values is a dictionary containing:
                - base_amount:  float
                - tax_amount:   float
        :param options_list:        The report options list, first one being the current dates range, others being the
                                    comparisons.
        :param expanded_account:    An optional account.account record that must be specified when expanding a line
                                    with of without the load more.
        :param fetch_lines:         A flag to fetch the account.move.lines or not (the 'lines' key in accounts_values).
        :return:                    (accounts_values, taxes_results)
        '''
        # Execute the queries and dispatch the results.
        options_list[0].update(strict_range=True)
        query, params = self._get_query_sums(options_list, expanded_account=expanded_account)

        groupby_accounts = {}
        groupby_companies = {}
        groupby_taxes = {}

        self.env.cr.execute(query, params)
        return self._cr.dictfetchall()
    # ####################################################
    # # COLUMN/LINE HELPERS
    # ####################################################
    #
    @api.model
    def _get_account_title_line(self, options, account, amount_currency, debit, credit, balance, has_lines):
        unfold_all = self._context.get('print_mode') and not options.get('unfolded_lines')

        name = '%s %s' % (account.code, account.name)
        columns = [
            {'name': self.format_value(debit), 'class': 'number'},
            {'name': self.format_value(credit), 'class': 'number'},
            {'name': self.format_value(balance), 'class': 'number'},
        ]
        if self.user_has_groups('base.group_multi_currency'):
            has_foreign_currency = account.currency_id and account.currency_id != account.company_id.currency_id or False
            columns.insert(0, {'name': has_foreign_currency and self.format_value(amount_currency, currency=account.currency_id, blank_if_zero=True) or '', 'class': 'number'})
        return {
            'id': 'account_%d' % account.id,
            'name': name,
            'code': account.code,
            'columns': columns,
            'level': 1,
            'unfoldable': has_lines,
            'unfolded': has_lines and 'account_%d' % account.id in options.get('unfolded_lines') or unfold_all,
            'colspan': 4,
            'class': 'o_account_reports_totals_below_sections' if self.env.company.totals_below_sections else '',
        }



    @api.model
    def _get_aml_line(self, options, aml):
        currency_id = False
        if aml['currency_id'] is not None:
            currency_id = self.env['res.currency'].browse(aml['currency_id'])
        columns = [
            {'name': self._format_aml_name(aml['name'], aml['ref']), 'class': 'o_account_report_line_ellipsis'},
            {'name': aml['name'], 'class': 'o_account_report_line_ellipsis'},
            {'name': aml['business_name'], 'class': 'o_account_report_line_ellipsis'},
            {'name': aml['ref'], 'class': 'o_account_report_line_ellipsis'},
            {'name': aml['partner_name'], 'class': 'o_account_report_line_ellipsis'},
            {'name': self.format_value(aml['revenue'], blank_if_zero=True), 'class': 'number'},
            {'name': format_date(self.env, aml['date']), 'class': 'date'},
            {'name': self.with_context(no_format=False).format_value(aml['amount_currency'], currency=currency_id, blank_if_zero=True) , 'class': 'number'},
            {'name': self.format_value(aml.get('fct_revenue', 0) or 0, blank_if_zero=True), 'class': 'number'},
            {'name': aml.get('fct_perc'), 'class': 'number'},
            {'name': self.format_value(aml.get('fct_vat', 0) or 0, blank_if_zero=True), 'class': 'number'},
            {'name': self.format_value(aml.get('cit_revenue', 0) or 0, blank_if_zero=True), 'class': 'number'},
            {'name': aml.get('cit_perc') or 0, 'class': 'number'},
            {'name': self.format_value(aml.get('cit_vat', 0) or 0, blank_if_zero=True), 'class': 'number'},
            {'name': self.format_value((aml.get('cit_vat', 0) or 0) + (aml.get('fct_vat', 0) or 0), blank_if_zero=True), 'class': 'number'},
        ]
        # if self.user_has_groups('base.group_multi_currency'):
        #     if (aml['currency_id'] and aml['currency_id'] != account.company_id.currency_id.id) or account.currency_id:
        #         currency = self.env['res.currency'].browse(aml['currency_id'])
        #     else:
        #         currency = False
        #     columns.insert(3, {'name': currency and aml['amount_currency'] and self.format_value(aml['amount_currency'], currency=currency, blank_if_zero=True) or '', 'class': 'number'})
        return {
            'id': aml['id'],
            # 'name': aml['name'],
            'columns': columns,
            'level': 1,
        }


    @api.model
    def _get_account_total_line(self, options, account, amount_currency, debit, credit, balance):

        columns = []
        if self.user_has_groups('base.group_multi_currency'):
            has_foreign_currency = account.currency_id and account.currency_id != account.company_id.currency_id or False
            columns.append({'name': has_foreign_currency and self.format_value(amount_currency, currency=account.currency_id, blank_if_zero=True) or '', 'class': 'number'})

        columns += [
            {'name': self.format_value(debit), 'class': 'number'},
            {'name': self.format_value(credit), 'class': 'number'},
            {'name': self.format_value(balance), 'class': 'number'},
        ]

        return {
            'id': 'total_%s' % account.id,
            'class': 'o_account_reports_domain_total',
            'parent_id': 'account_%s' % account.id,
            'name': _('Total %s', account["display_name"]),
            'columns': columns,
            'colspan': 4,
        }

    @api.model
    def _get_total_line(self, total_fct, total_cit, total_fct_revenue, total_cit_revenue, balance):
        return {
            'id': 'general_ledger_total_%s' % self.env.company.id,
            'name': _('Total'),
            'class': 'total',
            'level': 1,
            'columns': [
                {'name': ''},
                {'name': '', },
                {'name': '', },
                {'name': '', },
                {'name': '', },
                {'name': self.format_value(balance), 'class': 'number'},
                {'name': '',},
                {'name': '',},
                {'name': self.format_value(total_fct_revenue), 'class': 'number'},
                {'name': '', },
                {'name': self.format_value(total_fct), 'class': 'number'},
                {'name': self.format_value(total_cit_revenue), 'class': 'number'},
                {'name': '', },
                {'name': self.format_value(total_cit), 'class': 'number'},
                {'name': self.format_value(total_fct + total_cit), 'class': 'number'},
            ],
            'colspan': 1,
        }

    def get_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        date_default_col1_style = workbook.add_format(
            {'font_name': 'Tahoma', 'font_size': 12, 'font_color': '#000080', 'indent': 2, 'num_format': 'dd/mm/yyyy','text_wrap': True})
        date_default_style = workbook.add_format(
            {'font_name': 'Tahoma', 'font_size': 8, 'font_color': '#000080', 'num_format': 'dd/mm/yyyy',
             'bottom': 1, 'top': 1,'left': 1,'right': 1, 'text_wrap': True, 'align': 'center'})
        default_col1_style = workbook.add_format(
            {'font_name': 'Tahoma', 'font_size': 12, 'font_color': '#666666', 'indent': 2, 'text_wrap': True})
        default_style = workbook.add_format({'font_name': 'Tahoma', 'font_size': 12, 'font_color': '#666666', 'text_wrap': True})
        title_style_center = workbook.add_format({'font_name': 'Tahoma', 'font_color': '#000080', 'bg_color': '#D7D7D7', 'align': 'center', 'text_wrap': True, 'valign': 'vcenter',})
        title_style_left = workbook.add_format({'font_name': 'Tahoma',  'font_color': '#000080', 'bg_color': '#F0F0F0', 'align': 'left', 'text_wrap': True})
        title_style_right = workbook.add_format({'font_name': 'Tahoma',  'font_color': '#000080', 'bg_color': '#F0F0F0', 'align': 'left', 'text_wrap': True})
        title_style_size8 = workbook.add_format({'font_name': 'Tahoma',   'font_color': '#000080', 'font_size': 8, 'bg_color': '#F0F0F0', 'align': 'center', 'text_wrap': True})
        title_style_size8_right = workbook.add_format({'font_name': 'Tahoma',   'font_color': '#000080', 'font_size': 8, 'bg_color': '#F0F0F0', 'align': 'right', 'text_wrap': True})
        title_style_size8_left = workbook.add_format({'font_name': 'Tahoma',   'font_color': '#000080', 'font_size': 8, 'bg_color': '#F0F0F0', 'align': 'left', 'text_wrap': True})
        title_style_bold = workbook.add_format({'font_name': 'Tahoma', 'bold': True, 'bottom': 2, 'font_size': 11, 'text_wrap': True,
                                                'font_color': '#000080', 'bg_color': '#F0F0F0', 'align': 'center'})
        level_0_style = workbook.add_format(
            {'font_name': 'Tahoma', 'bold': True, 'font_size': 8, 'bottom': 1, 'top': 1,'left': 1,'right': 1,
             'font_color': '#000080', 'bg_color': '#D7D7D7', 'num_format': '#,##0', 'align': 'center', 'text_wrap': True, 'valign': 'vcenter'})

        level_0_style_white = workbook.add_format(
            {'font_name': 'Tahoma', 'bold': True, 'font_size': 8, 'bottom': 1, 'top': 1,'left': 1,'right': 1,
             'font_color': '#000080', 'num_format': '#,##0', 'align': 'center', 'text_wrap': True, 'valign': 'vcenter'})
        level_1_style = workbook.add_format(
            {'font_name': 'Tahoma', 'font_color': '#000080', 'bottom': 1, 'top': 1,'left': 1,'right': 1,
             'font_size': 8,  'num_format': '#,##0', 'text_wrap': True})
        level_1_style_bg = workbook.add_format(
            {'font_name': 'Tahoma', 'font_color': '#000080', 'bg_color': '#D7D7D7', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1,
             'font_size': 8, 'align': 'center'})
        level_2_col1_total_style = workbook.add_format(
            {'font_name': 'Tahoma', 'bold': True, 'font_color': '#000080', 'bg_color': '#E9F5FE', 'bottom': 1, 'top': 1,'left': 1,'right': 1,
             'font_size': 8, 'text_wrap': True})
        level_2_style = workbook.add_format(
            {'font_name': 'Tahoma', 'font_color': '#000080', 'bg_color': '#E9F5FE', 'bottom': 1, 'top': 1,'left': 1,'right': 1,
             'font_size': 8,  'num_format': '#,##0', 'text_wrap': True, 'bold': True,})
        level_3_col1_style = workbook.add_format(
            {'font_name': 'Tahoma', 'font_size': 12, 'font_color': '#666666', 'indent': 2, 'text_wrap': True})
        level_3_col1_total_style = workbook.add_format(
            {'font_name': 'Tahoma', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1, 'text_wrap': True})
        level_3_style = workbook.add_format({'font_name': 'Tahoma', 'font_size': 12, 'font_color': '#666666', 'text_wrap': True})

        # # Set the first column width to 50
        sheet.set_column(0, 1, 4)
        sheet.set_column(2, 2, 20)
        sheet.set_column(3, 3, 10)
        sheet.set_column(4, 4, 45)
        sheet.set_column(5, 5, 20)
        sheet.set_column(6, 7, 15)
        sheet.set_column(8, 8, 20)
        sheet.set_column(9, 9, 15)
        sheet.set_column(10, 10, 20)
        sheet.set_column(11, 11, 8)
        sheet.set_column(12, 13, 20)
        sheet.set_column(14, 14, 8)
        sheet.set_column(15, 17, 20)

        y_offset = 0
        date_to = datetime.strptime(options.get('date').get('date_to'), '%Y-%m-%d')
        headers, lines = self.with_context(no_format=True, print_mode=True, prefetch_fields=False)._get_table(options)
        sheet.merge_range(y_offset, 0, y_offset, 16,'TỜ KHAI THUẾ NHÀ THẦU NƯỚC NGOÀI (Mẫu số 03/NTNN)', title_style_bold)
        y_offset += 1

        sheet.merge_range(y_offset, 0, y_offset, 16,'(Áp dụng đối với nhà thầu nước ngoài trực tiếp nộp thuế TNDN theo tỷ lệ %  trên doanh thu tính thuế)', title_style_size8)
        y_offset += 1
        sheet.write(y_offset, 7, '[01]  Kỳ tính thuế: ', title_style_size8)
        sheet.write(y_offset, 8, ' [x] Tháng  năm %s'%date_to.year, title_style_size8)
        y_offset += 1
        sheet.write(y_offset, 7, '[02]  Lần đầu', title_style_size8_right)
        sheet.write(y_offset, 8, '[ ]', title_style_size8_left)
        sheet.merge_range(y_offset, 9, y_offset, 10, '[03] Bổ sung lần thứ ', title_style_size8)
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[04] Tên người nộp thuế:', title_style_left)
        sheet.merge_range(y_offset, 3, y_offset, 5, self.env.company.name, title_style_left)
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[05] Mã số thuế :', title_style_left)
        sheet.merge_range(y_offset, 3, y_offset, 5, self.env.company.fct_code, title_style_left)
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[06] Tên đại lý thuế (nếu có): ', title_style_left)
        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset, 2, '[07] Mã số thuế:', title_style_left)
        sheet.merge_range(y_offset, 15, y_offset, 16, 'Đơn vị tiền: Đồng Việt Nam:', title_style_right)


        y_offset += 1
        sheet.merge_range(y_offset, 1, y_offset + 1, 1, 'STT', level_0_style)
        sheet.merge_range(y_offset, 2, y_offset, 4, 'Nội dung', level_0_style)
        sheet.merge_range(y_offset, 6, y_offset, 7, 'Hợp đồng', level_0_style)
        sheet.merge_range(y_offset, 9, y_offset, 11, 'Thuế giá trị gia tăng (GTGT)', level_0_style)
        sheet.merge_range(y_offset, 12, y_offset, 15, 'Thuế thu nhập doanh nghiệp (TNDN)', level_0_style)

        y_offset += 1
        sheet.write(y_offset, 2, 'Tên nhà thầu', level_0_style)
        sheet.write(y_offset, 3, 'Mã ngành nghề', level_0_style)
        sheet.write(y_offset, 4, 'Tên ngành nghề', level_0_style)
        sheet.merge_range(y_offset - 1, 5, y_offset, 5,'Mã số thuế của NTNN tại Việt Nam (nếu có)', level_0_style)
        sheet.write(y_offset, 6, 'Số', level_0_style)
        sheet.write(y_offset, 7, u'Ngày/tháng/Năm', level_0_style)
        sheet.merge_range(y_offset - 1, 8, y_offset, 8, 'Doanh thu chưa bao gồm thuế GTGT', level_0_style)
        sheet.write(y_offset, 9, 'Ngày thanh toán', level_0_style)
        sheet.write(y_offset, 10, u'Doanh thu tính thuế', level_0_style)
        sheet.write(y_offset, 11, u'Tỷ lệ % để tính thuế GTGT', level_0_style)
        sheet.write(y_offset, 12, 'Thuế giá trị gia tăng phải nộp', level_0_style)
        sheet.write(y_offset, 13, 'Doanh thu tính thuế', level_0_style)
        sheet.write(y_offset, 14, 'Tỷ lệ (%) thuế TNDN', level_0_style)
        sheet.write(y_offset, 15, 'Số thuế  được miễn giảm theo Hiệp định', level_0_style)
        sheet.write(y_offset, 16, 'Thuế thu nhập doanh nghiệp phải nộp', level_0_style)
        sheet.merge_range(y_offset - 1, 17, y_offset, 17, 'Tổng số thuế phải nộp vào Ngân sách Nhà nước', level_0_style)
        y_offset += 1

        sheet.write(y_offset, 1, '', level_1_style_bg)
        sheet.write(y_offset, 2, '(1a)', level_1_style_bg)
        sheet.write(y_offset, 3, '', level_1_style_bg)
        sheet.write(y_offset, 4, '(1b)', level_1_style_bg)
        sheet.write(y_offset, 5, '(2)', level_1_style_bg)
        sheet.write(y_offset, 6, '(3)', level_1_style_bg)
        sheet.write(y_offset, 7, '(4)', level_1_style_bg)
        sheet.write(y_offset, 8, '(5)', level_1_style_bg)
        sheet.write(y_offset, 9, '(6)', level_1_style_bg)
        sheet.write(y_offset, 10, '(7)', level_1_style_bg)
        sheet.write(y_offset, 11, '(8)', level_1_style_bg)
        sheet.write(y_offset, 12, '(9=7x8)', level_1_style_bg)
        sheet.write(y_offset, 13, '(10)', level_1_style_bg)
        sheet.write(y_offset, 14, '(11)', level_1_style_bg)
        sheet.write(y_offset, 15, '(12)', level_1_style_bg)
        sheet.write(y_offset, 16, '[13=(10x11)-(12)]', level_1_style_bg)
        sheet.write(y_offset, 17, '(14)=(9)+(13)', level_1_style_bg)
        # Add headers.
        # for header in headers:
        #     x_offset = 1
        #     sheet.write(y_offset, 0, 'No.', title_style_left)
        #
        #     for column in header:
        #         column_name_formated = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
        #         colspan = column.get('colspan', 1)
        #         if colspan == 1:
        #             sheet.write(y_offset, x_offset, column_name_formated, title_style)
        #         else:
        #             sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1, column_name_formated,
        #                               title_style)
        #         x_offset += colspan
        #     y_offset += 1

        if options.get('hierarchy'):
            lines = self._create_hierarchy(lines, options)
        if options.get('selected_column'):
            lines = self._sort_lines(lines, options)

        # Add lines.
        stt = 1

        #define columns position follow data get
        position = {'partner': 4,
                    'code': 1,
                    'detail': 2,
                    'company_fct_code': self.env.company.fct_code,
                    'detail_ref': 3,
                    'date': 6,
                    'total_amount': 5,
                    'payment_date': 6,
                    'revenue_vat': 8,
                    'percent_vat': 9,
                    'fct_vat': 10,
                    'revenue_cit': 11,
                    'percent_cit': 12,
                    'deduct_tax': '0',
                    'vat_cit': 13,
                    'total': 14,
                    }

        for y in range(0, len(lines)):
            y_offset += 1
            if y == len(lines) - 1:
                style = level_2_style
            else:
                style = level_1_style
            # write the first column, with a specific style to manage the indentation
            if y < len(lines) - 1:
                sheet.write(y_offset, 1, stt, style)
                stt += 1
            else:
                sheet.write(y_offset, 1, '', style)

            # write all the remaining cells
            x = 2
            for key, value in position.items():
                if type(value) is not int:
                    sheet.write(y_offset, x, value if y != len(lines) - 1 else '', style)
                    if y == len(lines) - 1:
                        sheet.write(y_offset, 2, 'Tổng cộng: ', level_2_col1_total_style)
                    x += 1
                    continue
                cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][value])
                if y == len(lines) - 1:
                    if type(cell_value) is not float and type(cell_value) is not int:
                        sheet.write(y_offset, x, '', style)
                        x += 1
                        continue
                if cell_type == 'date':
                    sheet.write_datetime(y_offset, x , cell_value,
                                         date_default_style)
                else:
                    sheet.write(y_offset, x, cell_value, style)
                x += 1
        y_offset += 2
        sheet.write(y_offset, 2, 'NHÂN VIÊN ĐẠI LÝ THUẾ', level_0_style)
        y_offset += 1
        sheet.write(y_offset, 2, 'Họ và tên:', level_0_style)
        sheet.merge_range(y_offset, 4, y_offset, 6, '', level_0_style_white)
        sheet.write(y_offset, 11, 'Người ký:', level_0_style)
        sheet.merge_range(y_offset, 12, y_offset, 14, '', level_0_style_white)
        y_offset += 1
        sheet.write(y_offset, 2, 'Chứng chỉ hành nghề số:', level_0_style)
        sheet.merge_range(y_offset, 4, y_offset, 6, '', level_0_style_white)
        sheet.write(y_offset, 11, 'Ngày ký:', level_0_style)
        sheet.merge_range(y_offset, 12, y_offset, 14, format_date(self.env, datetime.today()), level_0_style_white)

        # fct_vat = lines[y]['columns'][position.get('')]

            # for x in range(1, len(lines[y]['columns']) + 1):
            #     cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][x - 1])
            #     if cell_type == 'date':
            #         sheet.write_datetime(y + y_offset, x + lines[y].get('colspan', 1), cell_value,
            #                              date_default_style)
            #     else:
            #         sheet.write(y + y_offset, x + lines[y].get('colspan', 1), cell_value, level_1_style)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file
