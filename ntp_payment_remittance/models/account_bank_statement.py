from datetime import timedelta
import logging
import re

from odoo import fields, api, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, date_utils
from odoo.tools.misc import formatLang

logger = logging.getLogger(__name__)


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    is_show_button_soft_reset = fields.Boolean(compute="_compute_show_custom_button", store=False)
    is_show_button_import_line = fields.Boolean(compute="_compute_show_custom_button", store=False)

    def _compute_show_custom_button(self):
        for rec in self:
            rec.is_show_button_soft_reset = True
            rec.is_show_button_import_line = rec.journal_id.type == 'bank'

    @api.model
    def online_sync_sms_bank_statement(self, transactions, bank_sms, journal_ids, bank_account_type):
        """
        same as _online_sync_bank_statement but we work for sms transaction data

        journal_ids => this is just 1 journal but I am still consider the effective way to since bank.statement now

        Warning:
        ========

        data got from bank sms is little different with data we got from online sync,
        we can have balance notification for every transaction

        however, we will also have another problem since ifttt is not reliable, we may
        face some gap between 2 transactions (missing some transactions, or some fee charged to our account not reported by sms)

        """
        # fmt: on
        line_to_reconcile = self.env['account.bank.statement.line']
        for journal in journal_ids:
            # Since the synchronization succeeded, set it as the bank_statements_source of the journal
            journal.sudo().write({'bank_statements_source': 'bank_sms'})
            if not transactions:
                continue

            transactions_identifiers = [line['online_transaction_identifier'] for line in transactions]
            existing_transactions_ids = self.env['account.bank.statement.line'].search([('online_transaction_identifier', 'in', transactions_identifiers), ('journal_id', '=', journal.id)])
            existing_transactions = [t.online_transaction_identifier for t in existing_transactions_ids]

            transactions_partner_information = []
            for transaction in transactions:
                transaction['date'] = fields.Datetime.from_string(transaction['date'])
                if transaction.get('online_partner_information'):
                    transactions_partner_information.append(transaction['online_partner_information'])

            if transactions_partner_information:
                self._cr.execute("""
                    SELECT p.online_partner_information, p.id FROM res_partner p
                    WHERE p.online_partner_information IN %s
                """, [tuple(transactions_partner_information)])
                partner_id_per_information = dict(self._cr.fetchall())
            else:
                partner_id_per_information = {}

            sorted_transactions = sorted(transactions, key=lambda l: l['date'])

            for id, transaction in enumerate(sorted_transactions):
                transaction['sequence'] = id

            #
            first_transaction = sorted_transactions[0]
            if bank_account_type == "bank":
                openning_balance = first_transaction['balance'] - first_transaction['amount']
                closing_balance = bank_sms.get_balance(journal)
            else:
                openning_balance = 0
                closing_balance = 0

            min_date = date_utils.start_of(sorted_transactions[0]['date'], 'month')
            if journal.bank_statement_creation_groupby == 'week':
                # key is not always the first of month
                weekday = min_date.weekday()
                min_date = date_utils.subtract(min_date, days=weekday)
            max_date = sorted_transactions[-1]['date']
            total = sum([t['amount'] for t in sorted_transactions])

            statements_in_range = self.search([('date', '>=', min_date), ('journal_id', '=', journal.id)])

            # For first synchronization, an opening bank statement is created to fill the missing bank statements
            all_statement = self.search_count([('journal_id', '=', journal.id)])
            digits_rounding_precision = journal.currency_id.rounding if journal.currency_id else journal.company_id.currency_id.rounding
            # If there are neither statement and the ending balance != 0, we create an opening bank statement
            if all_statement == 0 and not float_is_zero(openning_balance, precision_rounding=digits_rounding_precision):
                opening_transaction = [(0, 0, {
                    'date': date_utils.subtract(min_date, days=1),
                    'payment_ref': _("Opening statement: first synchronization"),
                    'amount': openning_balance,
                    'balance': openning_balance,
                })]
                op_stmt = self.create({
                    'date': date_utils.subtract(min_date, days=1),
                    'line_ids': opening_transaction,
                    'journal_id': journal.id,
                    'balance_end_real': openning_balance,
                })
                op_stmt.button_post()
                line_to_reconcile += op_stmt.mapped('line_ids')

            transactions_in_statements = []
            statement_to_recompute = self.env['account.bank.statement']
            transactions_to_create = {}

            for transaction in sorted_transactions:
                if transaction['online_transaction_identifier'] and transaction['online_transaction_identifier'] in existing_transactions:
                    continue # Do nothing if the transaction already exists
                if bank_account_type != 'bank' and 'MISSING TRANSACTIONS - AMOUNT' in transaction['payment_ref']:
                    # we dont use gap here, so just ignore it when import
                    continue
                line = transaction.copy()
                if journal.bank_statement_creation_groupby == 'day':
                    # key is full date
                    key = transaction['date']
                elif journal.bank_statement_creation_groupby == 'week':
                    # key is first day of the week
                    weekday = transaction['date'].weekday()
                    key = date_utils.subtract(transaction['date'], days=weekday)
                elif journal.bank_statement_creation_groupby == 'bimonthly':
                    if transaction['date'].day >= 15:
                        # key is the 15 of that month
                        key = transaction['date'].replace(day=15)
                    else:
                        # key if the first of the month
                        key = date_utils.start_of(transaction['date'], 'month')
                    # key is year-month-0 or year-month-1
                elif journal.bank_statement_creation_groupby == 'month':
                    # key is first of the month
                    if not journal.monthly_statement_start_date:
                        key = date_utils.start_of(transaction['date'], 'month')
                    else:
                        # this is special case for credit payment which has closing statement different per each bank
                        # and user
                        key = transaction['date'].replace(day=journal.monthly_statement_start_date)
                elif journal.bank_statement_creation_groupby == 'custom':
                    # E.g: 1,11, and transaction date is 3 -> should go to 1 since 1<=3<11
                    days = [int(x) for x in journal.bank_statement_creation_custom.split(",")]
                    days = sorted(days, key=lambda x: x)
                    day_transaction = transaction['date'].day
                    days_filtered = [x for x in days if x <= day_transaction]
                    if days_filtered:
                        key = transaction['date'].replace(day=days_filtered[-1])
                    else:
                        # 5,10,15
                        # -> trx date is 16/Apr -> key is 15/Mar
                        # -> trx date is 1/Apr -> key is 15/Mar, not 15/Apr
                        # also special case for Jan -> Dec of previous year
                        key = transaction['date'].replace(day=days[-1])
                        if key.month == 1:
                            key = key.replace(month=12, year=key.year-1)
                        else:
                            key.month -= 1
                else:
                    # key is last date of transactions fetched
                    key = max_date
                # convert_key to date
                key = key.date()
                logger.info(f"{journal.name}: transaction {transaction['date']} -> stmt start date {key}")
                # Find partner id if exists
                if line.get('online_partner_information'):
                    partner_info = line['online_partner_information']
                    if partner_id_per_information.get(partner_info):
                        line['partner_id'] = partner_id_per_information[partner_info]

                # Decide if we have to update an existing statement or create a new one with this line
                stmt = statements_in_range.filtered(lambda x: x.date == key)
                if stmt and len(stmt.line_ids):
                    # check max sequence of line in current statement
                    max_sequence = max([x.sequence for x in stmt.line_ids])
                    line['statement_id'] = stmt[0].id
                    line['sequence'] += max_sequence
                    transactions_in_statements.append(line)
                    statement_to_recompute += stmt[0]
                    # in case of debit card, auto create opposite amount of value to make balance = 0
                    if bank_account_type == 'debit_card':
                        line_paid = line.copy()
                        line_paid['payment_ref'] = "Debit Card Payment: {}".format(line_paid['payment_ref'])
                        line_paid['amount'] = - line_paid['amount']
                        line_paid['sequence'] += 1
                        line_paid['online_transaction_identifier'] = False
                        transactions_in_statements.append(line_paid)
                else:
                    if not transactions_to_create.get(key):
                        transactions_to_create[key] = []
                    line['sequence'] = len(transactions_to_create[key])
                    transactions_to_create[key].append((0, 0, line))
                    # in case of debit card, auto create opposite amount of value to make balance = 0
                    if bank_account_type == 'debit_card':
                        line_paid = line.copy()
                        line_paid['payment_ref'] = "Debit Card Payment: {}".format(line_paid['payment_ref'])
                        line_paid['amount'] = - line_paid['amount']
                        line_paid['sequence'] = len(transactions_to_create[key])
                        line_paid['online_transaction_identifier'] = False
                        transactions_to_create[key].append((0, 0, line_paid))

            # Create the lines that should be inside an existing bank statement and reset those stmt in draft
            if transactions_in_statements:
                statement_to_recompute.write({'state': 'open'})
                line_to_reconcile += self.env['account.bank.statement.line'].create(transactions_in_statements)
                # Recompute the balance_end_real of the first statement where we added line
                # because adding line don't trigger a recompute and balance_end_real is not updated.
                # We only trigger the recompute on the first element of the list as it is the one
                # the most in the past and this will trigger the recompute of all the statements
                # that are next.
                statement_to_recompute[0]._compute_ending_balance()
                # Since the balance end real of the latest statement is not recomputed, we will
                # have a problem as balance_end_real and computed balance won't be the same and therefore
                # we will have an error while trying to post the entries. To prevent that error,
                # we force the balance_end_real of the latest statement to be the same as the computed
                # balance. Balance_end_real will be changed at the end of this method to match
                # the real balance of the account anyway so this is no big deal.
                statement_to_recompute[-1].balance_end_real = statement_to_recompute[-1].balance_end
                # # NOTE: smart reorder
                # statement_to_recompute.action_smart_reorder()
                # Post the statement back
                statement_to_recompute.button_post()

            # Create lines inside new bank statements
            created_stmts = self.env['account.bank.statement']
            for date, lines in transactions_to_create.items():
                # balance_start and balance_end_real will be computed automatically
                created_stmts += self.env['account.bank.statement'].create({
                    'date': date,
                    'line_ids': lines,
                    'journal_id': journal.id,
                })

            # NOTE: smart reorder
            # created_stmts.action_smart_reorder()
            created_stmts.button_post()
            line_to_reconcile += created_stmts.mapped('line_ids')
            # write account balance on the last statement of the journal
            # That way if there are missing transactions, it will show in the last statement
            # and the day missing transactions are fetched or manually written, everything will be corrected
            if bank_account_type == 'bank':
                last_bnk_stmt = self.search([('journal_id', '=', journal.id)], limit=1)
                if last_bnk_stmt and (created_stmts or transactions_in_statements):
                    last_bnk_stmt.balance_end_real = closing_balance
            # Set last sync date as the last transaction date
            journal.account_online_account_id.sudo().write({'last_sync': max_date})

            # NOTE: smart reorder
            if bank_account_type == 'bank':
                for stmt in created_stmts:
                    created_stmts.button_smart_reorder()
                last_bnk_stmt = self.search([('journal_id', '=', journal.id)], limit=1)
                if last_bnk_stmt and (created_stmts or transactions_in_statements):
                    last_bnk_stmt.button_smart_reorder()

        return line_to_reconcile
    # fmt: off

    def import_transactions(self):
        self.ensure_one()

    def button_soft_reopen(self):
        self.ensure_one()
        if any(statement.state == 'draft' for statement in self):
            raise UserError(_("Only validated statements can be reset to new."))

        self.write({'state': 'open'})

    def button_smart_reorder(self):
        for rec in self:
            try:
                rec.write({'state': 'open'})
                rec._action_smart_reorder()
                # we can trust it since all entries have balance, so the lastone will be current balance
                rec.balance_end_real = rec.balance_end
                sequences = rec.line_ids.mapped('sequence')
                last = max(sequences)
                last_balance = rec.line_ids[sequences.index(last)].balance
                if rec.balance_end_real != last_balance:
                    rec.message_post(body=f"Balance End {rec.balance_end_real} is not matched with last transaction information {last_balance}")
                rec.button_post()
            except Exception as e:
                logger.error(e, exc_info=True)

    def action_smart_reorder(self):
        for rec in self:
            rec._action_smart_reorder()

    def _action_smart_reorder(self):
        self.ensure_one()
        # filter date by date in current statement
        non_gap_trx = []

        # STEP 1: remove all gap trx
        for _id, line in enumerate(self.line_ids):
            if _id == 0:
                non_gap_trx.append(line)
                continue
            # FIXME: how about balance is really is 0 :D
            if 'GAP' in str(line.narration) or line.balance == 0:
                continue
            non_gap_trx.append(line)
        # STEP 2: sort by date and sequence (respect the order we saved first, but must follow date + sequence)
        def sorting_trx(line):
            sequence = line.sequence if line.sequence else 0
            return int(line.date.strftime('%s')) + sequence
        sorted_non_gap_trx = sorted(non_gap_trx, key=sorting_trx)

        # STEP 3: Smart order
        def _get_possible_position_to_insert(trx_list, trx_to_add):
            pos = []
            for _id, trx in enumerate(trx_list):
                if _id == 0:
                    continue
                if trx.date == trx_to_add.date:
                    pos.append(_id)
            if pos:
                # append case
                append_pos = max(pos) + 1
                pos.append(append_pos)
            else:
                pos.append(len(trx_list))
            return list(set(pos))

        def _calc_total_gap(trx_list):
            gaps = []
            for _id, trx in enumerate(trx_list):
                if _id == 0:
                    continue
                gap = trx.balance - trx.amount - trx_list[_id - 1].balance
                gaps.append(gap)
            total_gap = sum([abs(x) for x in gaps])
            return total_gap

        reordered_trx = []
        for _id, line in enumerate(sorted_non_gap_trx):
            if _id == 0 or _id == len(sorted_non_gap_trx) - 1:
                reordered_trx.append(line)
                continue
            gap_data = {}
            possible_pos = _get_possible_position_to_insert(reordered_trx, line)
            for pos in possible_pos:
                possible_reordered_trx = reordered_trx.copy()
                possible_reordered_trx.insert(pos, line)
                gap_data[pos] = _calc_total_gap(possible_reordered_trx)
            sorted_gap_data = sorted(gap_data.items(), key=lambda item: item[1])
            pos_to_add = sorted_gap_data[0][0]
            # add to reodered result
            # self.print_statement_lines(reordered_trx)
            reordered_trx.insert(pos_to_add, line)
            # self.print_statement_lines(reordered_trx)
            print(1)

        # STEP 4: delete all gap existed, and fill new gap which is best selection case
        ids_to_keep = [trx.id for trx in reordered_trx]
        gaps_to_create = []
        self.line_ids.filtered(lambda trx: trx.id not in ids_to_keep).unlink()
        #
        sequence = 0
        for _id, trx in enumerate(reordered_trx.copy()):
            if _id == 0:
                sequence += 1
                trx.sequence = sequence
                continue
            gap = trx.balance - trx.amount - reordered_trx[_id - 1].balance
            if not gap:
                sequence += 1
                trx.sequence = sequence
            else:
                #  gap is prev gap
                sequence += 1
                gaps_to_create.append(
                    {
                        'sequence': sequence,
                        "date": trx.date,
                        "amount": gap,
                        "balance": reordered_trx[_id - 1].balance + gap,
                        "payment_ref": "MISSING TRANSACTIONS - AMOUNT: {}".format(formatLang(self.env, gap)),
                        "online_transaction_identifier": False,
                        "narration": "<b style='color: red'>GAP</b>",
                        "statement_id": self.id,
                    }
                )
                sequence += 1
                trx.sequence = sequence
        self.env['account.bank.statement.line'].sudo().create(gaps_to_create)
        self.print_statement_lines(self.line_ids, sort=True)


    def print_statement_lines(self, line_ids, sort=False):
        headers = ['sequence', 'date', 'payment_ref', 'note', 'amount', 'balance']
        data = []
        for trx in line_ids:
            data.append(
                [
                    trx.sequence,
                    trx.date,
                    trx.payment_ref,
                    'GAP' if 'GAP' in str(trx.narration) else '',
                    formatLang(self.env, trx.amount),
                    formatLang(self.env, trx.balance),
                ]
            )
        from tabulate import tabulate
        if sort:
            data = sorted(data, key=lambda x: x[0])
        print("\n{}".format(tabulate(data, headers=headers, tablefmt='psql')))


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    # balance = fields.Monetary("Balance", compute="_compute_balance", store=False)
    balance = fields.Monetary("Balance")
    previous_balance = fields.Monetary("Prev Balance", compute="_compute_prev_balance")
    internal_transfer_created = fields.Boolean()
    may_be_internal_transfer = fields.Boolean(compute="_compute_internal_transfer", store=False)

    def _compute_internal_transfer(self):

        get_param = self.env["ir.config_parameter"].sudo().get_param
        always_show_internal_transfer_button = get_param("ntp_payment_remittance.always_show_internal_transfer_button")
        show_internal_transfer_button_from = get_param("ntp_payment_remittance.show_internal_transfer_button_from")
        internal_transfer_patterns = get_param("ntp_payment_remittance.internal_transfer_patterns")

        def can_be_internal_transfer(rec):
            if not rec.payment_ref:
                return False
            if rec.is_gap() or rec.internal_transfer_created:
                return False
            if always_show_internal_transfer_button:
                return True
            # only show when not gap and check how transfer button can be shown
            if show_internal_transfer_button_from == 'sender' and rec.amount > 0:
                return False
            if show_internal_transfer_button_from == 'receiver' and rec.amount < 0:
                return False
            if internal_transfer_patterns:
                pattern_list = internal_transfer_patterns.split("\n")
                for pattern in pattern_list:
                    if re.match(pattern, rec.payment_ref, re.IGNORECASE):
                        return True
            return False

        for rec in self:
            rec.may_be_internal_transfer = False
            if can_be_internal_transfer(rec):
                rec.may_be_internal_transfer = True

    def _compute_prev_balance(self):
        for rec in self:
            rec.previous_balance = rec.balance - rec.amount
    
    def is_gap(self):
        self.ensure_one()
        if 'MISSING TRANSACTIONS' in self.payment_ref:
            return True
        return False

    def button_call_interal_transfer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Create Internal Transfer",
            "res_model": "internal.transfer.create",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_statement_id": self.statement_id.id,
                "default_statement_line_id": self.id,
            },
        }

    def button_reset_internal_transfer_state(self):
        self.internal_transfer_created = False

    def button_skip_internal_transfer(self):
        for rec in self:
            self.internal_transfer_created = True
