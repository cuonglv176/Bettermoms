import re
import logging
import base64
import codecs
import io
import chardet
import psycopg2
import unicodedata
from odoo import tools
from odoo.addons.base_import.models.base_import import (
    DATE_PATTERNS,
    TIME_PATTERNS,
    check_patterns,
    to_re,
)
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import date_utils, pycompat
from datetime import datetime

logger = logging.getLogger(__name__)


BOM_MAP = {
    "utf-16le": codecs.BOM_UTF16_LE,
    "utf-16be": codecs.BOM_UTF16_BE,
    "utf-32le": codecs.BOM_UTF32_LE,
    "utf-32be": codecs.BOM_UTF32_BE,
}


def build_table_result(data_list: list):
    template = """
        <style>
            .styled-table {
                border-collapse: collapse;
                // margin: 25px 0;
                font-family: sans-serif;
                min-width: 400px;
                width: 100%;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            }
            .styled-table thead tr {
                background-color: #009879;
                color: #ffffff;
                text-align: left;
            }
            .styled-table th, .styled-table td {
                padding: 3px 10px;
            }
            .styled-table tbody tr {
                border-bottom: 1px solid #dddddd;
            }

            .styled-table tbody tr:nth-of-type(even) {
                background-color: #f3f3f3;
            }

            .styled-table tbody tr:last-of-type {
                border-bottom: 2px solid #009879;
            }

            .styled-table tbody tr.to_reconcile {
                color: red;
            }
        </style>

        <table class="styled-table">
        <thead>
            <tr>
                <td>#</td>
                <td style="min-width: 90px">Date</td>
                <td>Label</td>
                <!-- <td>Partner</td> -->
                <!-- <td>Reference</td> -->
                <!-- <td>Note</td> -->
                <td>Amount</td>
                <td>Balance</td>
                <td>Reconciled</td>
            </tr>
        </thead>
        <tbody>
    """
    total = 0
    for row in data_list:
        label = row["payment_ref"]
        if row["partner"]:
            label += f"<br/><code>Partner: {row['partner']}</code>"
        data = f"""
        <tr class="{'to_reconcile' if not row['is_reconciled'] else ''}">
            <td>{row['sequence']}</td>
            <td>{row['date']}</td>
            <td>{label}</td>
            <!-- <td>{row['partner']}</td> -->
            <!-- <td>{row['ref'] or ''}</td> -->
            <!-- <td>{row['note'] or ''}</td> -->
            <td>{row['amount_text']}</td>
            <td>{row['balance_text']}</td>
            <td>{row['is_reconciled']}</td>
        </tr>
        """.strip()
        total += float(row["amount"])
        template += data
    template += "</tbody></table>"
    return template


def print_debug(transaction_in_statement_correction):
    for row in transaction_in_statement_correction:
        try:
            id = row[0]
            statement_in_db = row[1]
            statement_in_import = row[2]
            print(f"--- {id} ---")
            if statement_in_db:
                print(
                    f"db     date: {statement_in_db.date}, amount: {statement_in_db.amount}, balance: {statement_in_db.balance}, ref: {statement_in_db.payment_ref}"
                )
            if statement_in_import:
                print(
                    f"import date: {statement_in_import['date']}, amount: {statement_in_import['amount']}, balance: {statement_in_import['balance']}, ref: {statement_in_import['payment_ref']}"
                )
        except Exception as e:
            pass


class AccountBankStatementLineImport(models.TransientModel):
    _name = "account.bank.statement.line.import"
    _description = "Manual Import Multi Transactions to Bank Statement"

    upload_file = fields.Binary("Upload File")
    upload_file_name = fields.Char("File Name")
    statement_type = fields.Selection(
        selection=[
            ("bank", "Bank"),
            ("credit_card", "Credit Card"),
            ("debit_card", "Debit Card"),
            ("credit_card_final", "Credit Card Final"),
            ("dedit_card_final", "Dedit Card Final"),
        ],
        default="bank",
        required=True,
    )
    card_number = fields.Char("Filter Card Number")
    result_preview = fields.Text()

    def _check_csv(self, filename):
        return filename and filename.lower().strip().endswith(".csv")

    def get_bank_statement(self):
        bank_statement = self.env["account.bank.statement"].browse(
            self._context.get("active_ids", [])
        )
        if not bank_statement:
            raise UserError("Invalid Bank Statement")
        return bank_statement

    @api.constrains("upload_file")
    def validate_upload_file(self):
        if not self._check_csv(self.upload_file_name):
            raise ValidationError("Not csv file")

    def _read_csv(self, csv_data, options):
        """Returns file length and a CSV-parsed list of all non-empty lines in the file.

        :raises csv.Error: if an error is detected during CSV parsing
        """
        encoding = options.get("encoding")
        if not encoding:
            encoding = options["encoding"] = chardet.detect(csv_data)[
                "encoding"
            ].lower()
            # some versions of chardet (e.g. 2.3.0 but not 3.x) will return
            # utf-(16|32)(le|be), which for python means "ignore / don't strip
            # BOM". We don't want that, so rectify the encoding to non-marked
            # IFF the guessed encoding is LE/BE and csv_data starts with a BOM
            bom = BOM_MAP.get(encoding)
            if bom and csv_data.startswith(bom):
                encoding = options["encoding"] = encoding[:-2]

        if encoding != "utf-8":
            csv_data = csv_data.decode(encoding).encode("utf-8")

        separator = options.get("separator")
        if not separator:
            # default for unspecified separator so user gets a message about
            # having to specify it
            separator = ","
            for candidate in (
                ",",
                ";",
                "\t",
                " ",
                "|",
                unicodedata.lookup("unit separator"),
            ):
                # pass through the CSV and check if all rows are the same
                # length & at least 2-wide assume it's the correct one
                it = pycompat.csv_reader(
                    io.BytesIO(csv_data),
                    quotechar=options["quoting"],
                    delimiter=candidate,
                )
                w = None
                for row in it:
                    width = len(row)
                    if w is None:
                        w = width
                    if width == 1 or width != w:
                        break  # next candidate
                else:  # nobreak
                    separator = options["separator"] = candidate
                    break

        csv_iterator = pycompat.csv_reader(
            io.BytesIO(csv_data), quotechar=options["quoting"], delimiter=separator
        )

        content = [row for row in csv_iterator if any(x for x in row if x.strip())]

        # return the file length as first value
        return len(content), content

    def _try_match_date_time(self, preview_values, options):
        # Or a date/datetime if it matches the pattern
        date_patterns = [options["date_format"]] if options.get("date_format") else []
        user_date_format = (
            self.env["res.lang"]._lang_get(self.env.user.lang).date_format
        )
        if user_date_format:
            try:
                to_re(user_date_format)
                date_patterns.append(user_date_format)
            except KeyError:
                pass
        date_patterns.extend(DATE_PATTERNS)
        match = check_patterns(date_patterns, preview_values)
        if match:
            options["date_format"] = match
            return ["date", "datetime"]

        datetime_patterns = (
            [options["datetime_format"]] if options.get("datetime_format") else []
        )
        datetime_patterns.extend(
            "%s %s" % (d, t) for d in date_patterns for t in TIME_PATTERNS
        )
        match = check_patterns(datetime_patterns, preview_values)
        if match:
            options["datetime_format"] = match
            return ["datetime"]

        return []

    def convert_to_dict(self, content, options):
        content_dict = []

        for transaction in content[1:]:
            if self.statement_type == "bank":
                transaction_dict = {
                    "date": transaction[0],
                    "transaction_type": transaction[1],
                    "debit": float(transaction[2].strip().replace(",", "")),
                    "credit": float(transaction[3].strip().replace(",", "")),
                    "balance": float(transaction[4].strip().replace(",", "")),
                    "payment_ref": transaction[5],
                }
                transaction_dict["previous_balance"] = (
                    transaction_dict["balance"]
                    - transaction_dict["credit"]
                    + transaction_dict["debit"]
                )
            elif self.statement_type in ["credit_card", "debit_card"]:
                transaction_dict = {
                    "date": transaction[0],
                    "transaction_type": transaction[7],
                    "debit": float(transaction[4].strip().replace(",", "")),
                    "credit": 0,
                    "balance": 0,
                    "payment_ref": "{} {}".format(transaction[1], transaction[5]),
                    "card_number": transaction[2],
                    "acquiring_status": transaction[8],
                }
            elif self.statement_type in ["credit_card_final", "dedit_card_final"]:
                # check valid row
                # | Trx.   Date |  Post Date |                Merchant               |    Country/City   |  Original Amount | Amount(VND) |
                # |     Card    |   Number   | 4696-76XX-XXXX-2140                   |  PARK JONG HYUN   |                  |             |
                # |  25-02-2022 | 01-03-2022 | GRAB                                  |  VN/HA NOI        |    VND 43,000.00 |     43,000  |
                # |  25-02-2022 | 01-03-2022 | GRAB                                  |  VN/HA NOI        |    VND 56,000.00 |     56,000  |
                # ...
                # |  07-03-2022 | 09-03-2022 | N477FETZR2                            |  IE/fb.me/ads     | VND 6,292,073.00 |  6,292,073  |
                # |             |            | Your Spend For This   Month           |                   |                  | 16,541,882  |
                # |  25-02-2022 | 10-03-2022 | Annual Fee                            |                   |   VND 183,333.00 |    201,666  |
                # |  25-02-2022 | 10-03-2022 | Annual Fee -   Exemption              |                   |                  |   -201,666  |
                # |             |            | Fees                                  |                   |                  |          0  |
                # |             |            | Billing Amount of the   Current Month |                   |                  | 16,541,882  |
                if not transaction[3].strip() or not transaction[4].strip():
                    continue
                transaction_dict = {
                    "date": transaction[0],
                    "post_date": transaction[1],
                    "transaction_type": None,
                    "debit": float(transaction[5].strip().replace(",", "")),
                    "credit": 0,
                    "balance": 0,
                    "payment_ref": "{} {} {}".format(
                        transaction[1], transaction[2], transaction[3]
                    ),
                    "card_number": None,
                    "acquiring_status": None,
                }
            else:
                raise UserError("please choose import option")
            transaction_dict["amount"] = (
                transaction_dict["credit"] - transaction_dict["debit"]
            )
            content_dict.append(transaction_dict)

        analyze_date_time = self._try_match_date_time(
            [x["date"] for x in content_dict[1:]], options=options
        )

        if "date_format" in options:
            fmt = options["date_format"]
        elif "datetime_format" in options:
            fmt = options["datetime_format"]
        else:
            raise ValidationError("Seems Transaction date not in any common formats")

        # convert to date data
        for transaction in content_dict:
            transaction["date"] = datetime.strptime(transaction["date"], fmt)
            if "post_date" in transaction:
                transaction["post_date"] = datetime.strptime(
                    transaction["post_date"], fmt
                )

        return content_dict

    def get_transaction_path(self, transaction_list):
        # convert date and amount
        list_of_possible_transaction_path = []
        fisrt_time = True
        for transaction in transaction_list:
            if not list_of_possible_transaction_path and fisrt_time:
                fisrt_time = False
                list_of_possible_transaction_path.append([transaction])
                continue
            if not list_of_possible_transaction_path:
                continue
            addded_transaction_path = None
            remove_transaction_paths = []
            for transaction_path in list_of_possible_transaction_path:
                # try find match balance of next transaction
                last_match = False
                first_match = False
                # check last match
                if transaction_path[-1]["balance"] == transaction["previous_balance"]:
                    last_match = True
                # check first match
                if transaction_path[0]["previous_balance"] == transaction["balance"]:
                    first_match = True
                # add to the path possible cases
                # and remove invalid cases
                if last_match:
                    transaction_path.append(transaction)
                elif first_match:
                    transaction_path.insert(0, transaction)
                elif last_match and first_match:
                    addded_transaction_path = transaction_path.copy()
                    transaction_path.append(transaction)
                    addded_transaction_path.insert(0, transaction)
                else:
                    remove_transaction_paths.append(transaction_path)
                # check head of not left match
            list_of_possible_transaction_path = list(
                filter(
                    lambda x: x not in remove_transaction_paths,
                    list_of_possible_transaction_path,
                )
            )

        # also validate of date order, should be asc
        if len(list_of_possible_transaction_path) > 1:
            transaction_path = None
            for _transaction_path in list_of_possible_transaction_path:
                date_list = [x["date"] for x in _transaction_path]
                # validate date_list is increment list
                prev_date = None
                valid = True
                for date_of_trx in date_list:
                    if prev_date == None:
                        prev_date = date_of_trx
                        continue

                    if date_of_trx < prev_date:
                        valid = False
                        break
                    prev_date = date_of_trx
                if not valid:
                    continue
                transaction_path = _transaction_path
                break
            if not transaction_path:
                raise ValidationError(
                    "Transactions data is invalid, Please check it carefully again"
                )
        else:
            transaction_path = list_of_possible_transaction_path[0]
        return transaction_path

    # TODO: need to fix for custom case
    def filter_transaction_by_bank_statement_creation_groupby(self, transaction_path):
        bank_statement = self.get_bank_statement()
        groupby = bank_statement.journal_id.bank_statement_creation_groupby
        if groupby == "day":
            _from = bank_statement.date
            _to = date_utils.add(_from, days=1)
            _check_transaction_date = lambda _trx: _from <= _trx["date"] < _to
        elif groupby == "week":
            _from = bank_statement.date
            _to = date_utils.add(_from, days=7)  # within 1 week
            _check_transaction_date = lambda _trx: _from <= _trx["date"] < _to
        elif groupby == "bimonthly":
            _from = bank_statement.date
            if bank_statement.date >= 15:
                _to = _from.replace(month=((_from.month + 1) % 12), day=1)
                if _from.month == 12:
                    _to = _from.replace(year=_from.year + 1)
            else:
                _to = _from.replace(day=14)
            _check_transaction_date = lambda _trx: _from <= _trx["date"] < _to
        elif groupby == "month":
            if (
                not bank_statement.journal_id.monthly_statement_start_date
                or bank_statement.journal_id.monthly_statement_start_date == 1
            ):
                _from = bank_statement.date
                _to = _from.replace(month=((_from.month + 1) % 12), day=1)
                if _from.month == 12:
                    _to = _from.replace(year=_from.year + 1)
                _check_transaction_date = lambda _trx: _from <= _trx["date"] < _to
            else:
                # special case when statment is conjunction of 2 month data
                _from = bank_statement.date
                _to = _from.replace(month=((_from.month + 1) % 12), day=_from.day)
                if _from.month == 12:
                    _to = _from.replace(year=_from.year + 1)
                _check_transaction_date = lambda _trx: _from <= _trx["date"] < _to
        else:
            _check_transaction_date = lambda _trx: True

        transaction_path_filter = []
        for transaction in transaction_path:
            # also force to date data
            _trx = transaction.copy()
            _trx["date"] = transaction["date"].date()
            if _check_transaction_date(_trx):
                transaction_path_filter.append(_trx)

        return transaction_path_filter

    def button_import(self):
        bank_statement = self.get_bank_statement()
        transactions = self.execute_merge()
        if transactions:
            # save import file
            self.env["ir.attachment"].create(
                {
                    "name": self.upload_file_name,
                    "type": "binary",
                    "res_id": self.get_bank_statement().id,
                    "res_model": "account.bank.statement",
                    "datas": self.upload_file,
                }
            )
        return {"type": "ir.actions.act_window_close"}

    def button_preview(self):
        self.result_preview = False
        transactions = self.execute_merge(dryrun=True)
        if transactions:
            self.result_preview = build_table_result(transactions)
            self._cr.commit()
            return {
                "type": "ir.actions.act_window",
                "name": self._description,
                "res_model": self._name,
                "res_id": self.id,
                "view_type": "form",
                "view_mode": "form",
                "target": "new",
                "context": self._context.copy(),
            }
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Error !"),
                    "message": "You cannot import some errors happen !",
                    "sticky": False,
                    "type": "danger",
                },
            }

        # if transactions:
        #     message = {
        #         "type": "ir.actions.client",
        #         "tag": "display_notification",
        #         "params": {
        #             "title": _("Welldone, Importable !"),
        #             "message": "Press import to import your bank transaction now !",
        #             "sticky": False,
        #             "type": "success",
        #         },
        #     }
        # else:
        #     message = {
        #         "type": "ir.actions.client",
        #         "tag": "display_notification",
        #         "params": {
        #             "title": _("Error !"),
        #             "message": "You cannot import some errors happen !",
        #             "sticky": False,
        #             "type": "danger",
        #         },
        #     }
        # return message

    def execute_merge(self, dryrun=False):
        if self.statement_type == "bank":
            return self.execute_merge_bank_stmt_acc(dryrun=dryrun)
        elif self.statement_type in ["credit_card", "debit_card"]:
            return self.execute_merge_card_stmt_acc(dryrun=dryrun)
        elif self.statement_type in ["credit_card_final", "dedit_card_final"]:
            return self.execute_merge_card_stmt_acc_final(dryrun=dryrun)
        else:
            raise UserError("please choose import type")

    def get_transaction_import_preview(self, bank_statement):
        transaction_in_db = []
        for stmt in bank_statement.line_ids:
            trx = {
                "sequence": stmt.sequence,
                "date": stmt.date,
                "partner": "",
                "payment_ref": stmt.payment_ref,
                "ref": stmt.ref,
                "note": stmt.narration,
                "amount": stmt.amount,
                "amount_text": tools.format_amount(
                    self.env, amount=stmt.amount, currency=stmt.currency_id
                ),
                "balance": stmt.balance,
                "balance_text": tools.format_amount(
                    self.env,
                    amount=stmt.balance if stmt.balance else 0,
                    currency=stmt.currency_id,
                ),
                "is_reconciled": stmt.is_reconciled,
                # "transaction_type": stmt.transaction_type,
            }
            if stmt.partner_id:
                trx["partner"] = stmt.partner_id.name
            transaction_in_db.append(trx)
        transaction_in_db = sorted(transaction_in_db, key=lambda x: x["sequence"])
        return transaction_in_db

    ###################
    # CREDIT/DEBIT CARD IMPORT BY UPLOAD (FINAL STATEMENT)
    ###################
    def execute_merge_card_stmt_acc_final(self, dryrun=False):
        options = {"quoting": '"', "encoding": "utf-8-sig"}
        transactions = []
        csv_data = base64.b64decode(self.upload_file)
        cnt, content = self._read_csv(csv_data, options)
        content_dict = self.convert_to_dict(content, options)
        transaction_path = content_dict
        # TODO: since this is final credit card statement -> all entry are in correct group by ??? IS IT CORRECT ?
        transaction_path_filter = (
            self.filter_transaction_by_bank_statement_creation_groupby(transaction_path)
        )
        bank_statement = self.get_bank_statement()
        transaction_in_statement = bank_statement.line_ids

        # because this is final statement, so all the entries in csv file is correct
        # and we have to follow it
        transaction_to_create = []
        transaction_to_update = []
        for transaction in transaction_path_filter:
            is_match = False
            for stmt in transaction_in_statement:
                if (
                    stmt.amount == transaction["amount"]
                    and stmt.date == transaction["date"]
                ):
                    is_match = True
                    transaction_to_update.append((stmt, transaction))
                    break
            if not is_match:
                transaction_to_create.append(
                    {
                        "date": transaction["date"],
                        "amount": transaction["amount"],
                        "payment_ref": transaction["payment_ref"],
                        "balance": transaction["balance"],
                        "transaction_type": transaction["transaction_type"],
                        "statement_id": bank_statement.id,
                    }
                )
                # add debit entry
                if self.statement_type == "dedit_card_final":
                    transaction_to_create.append(
                        {
                            "date": transaction["date"],
                            "amount": -transaction["amount"],
                            "payment_ref": "Debit Card Payment: {}".format(
                                transaction["payment_ref"]
                            ),
                            "balance": transaction["balance"],
                            'transaction_type': transaction['transaction_type'],
                            "statement_id": bank_statement.id,
                        }
                    )

        # validate all unlink statement is not reconciled
        self._cr.execute("SAVEPOINT account_bank_statement_line_import")
        bank_statement.write({"state": "open"})
        # remove all transactions not be updated => it is not correct transactions though
        updated_stmt_ids = [x.id for x, _ in transaction_to_update]
        to_delete_stmt_ids = bank_statement.line_ids.filtered(
            lambda x: x.id not in updated_stmt_ids
        )
        to_delete_stmt_ids.button_undo_reconciliation()
        to_delete_stmt_ids.unlink()
        self.env["account.bank.statement.line"].create(transaction_to_create)
        if transaction_to_update:
            for stmt, trx in transaction_to_update:
                if trx["payment_ref"] not in str(stmt["payment_ref"]):
                    stmt.update({"payment_ref": trx["payment_ref"]})
                if trx["balance"] != stmt["balance"]:
                    stmt.update({"balance": trx["balance"]})
        # resequence data
        lines = sorted(bank_statement.line_ids, key=lambda x: x.date)
        for _id, line in enumerate(lines, start=1):
            line.sequence = _id
        bank_statement._compute_ending_balance()
        bank_statement.balance_end_real = bank_statement.balance_end
        bank_statement.button_post()
        transaction_in_db = self.get_transaction_import_preview(bank_statement)

        try:
            if dryrun:
                self._cr.execute(
                    "ROLLBACK TO SAVEPOINT account_bank_statement_line_import"
                )
            else:
                self._cr.execute("RELEASE SAVEPOINT account_bank_statement_line_import")
        except psycopg2.InternalError:
            pass

        return transaction_in_db

    ###################
    # CREDIT/DEBIT CARD IMPORT BY UPLOAD (NOT FINAL STATEMENT)
    ###################
    def execute_merge_card_stmt_acc(self, dryrun=False):
        # base option for csv import
        options = {"quoting": '"', "encoding": "utf-8-sig"}
        transactions = []
        csv_data = base64.b64decode(self.upload_file)
        cnt, content = self._read_csv(csv_data, options)
        content_dict = self.convert_to_dict(content, options)
        if self.card_number:
            transaction_path = [
                x for x in content_dict if x["card_number"] == self.card_number
            ]
        else:
            transaction_path = content_dict
        transaction_path_filter = (
            self.filter_transaction_by_bank_statement_creation_groupby(transaction_path)
        )
        bank_statement = self.get_bank_statement()
        transaction_in_statement = bank_statement.line_ids
        # in this case, it is just simple case to merge them together, no need to take tracing data
        transaction_to_create = []
        transaction_to_update = []
        for transaction in transaction_path_filter:
            is_match = False
            for stmt in transaction_in_statement:
                if (
                    stmt.amount == transaction["amount"]
                    and stmt.date == transaction["date"]
                ):
                    is_match = True
                    transaction_to_update.append((stmt, transaction))
                    break
            if not is_match and "acquired" in transaction["acquiring_status"].lower():
                # 08/03/2022 00:00:05	N477FETZR2	2140	VND	6,292,073.00	Ireland Republic of/fb.me/ads	887934	Credit Purchase	    Slip Acquired
                # 05/03/2022 08:15:21	MSFT *	    2140	USD	2,284,002.00	Singapore/MSBILL.INFO	        365433	Credit Purchase	    Slip Acquired
                # 05/03/2022 07:34:44	MSFT *  	2140	USD	263,345.00	    Singapore/MSBILL.INFO	        308133	Credit Purchase	    Slip Acquired
                transaction_to_create.append(
                    {
                        "date": transaction["date"],
                        "amount": transaction["amount"],
                        "payment_ref": transaction["payment_ref"],
                        "balance": transaction["balance"],
                        "transaction_type": transaction["transaction_type"],
                        "statement_id": bank_statement.id,
                    }
                )
                if self.statement_type == "debit_card":
                    transaction_to_create.append(
                        {
                            "date": transaction["date"],
                            "amount": -transaction["amount"],
                            "payment_ref": "Debit Card Payment: {}".format(
                                transaction["payment_ref"]
                            ),
                            "balance": transaction["balance"],
                            # 'transaction_type': transaction['transaction_type'],
                            "statement_id": bank_statement.id,
                        }
                    )

        # validate all unlink statement is not reconciled
        self._cr.execute("SAVEPOINT account_bank_statement_line_import")
        bank_statement.write({"state": "open"})
        self.env["account.bank.statement.line"].create(transaction_to_create)
        if transaction_to_update:
            for stmt, trx in transaction_to_update:
                stmt.update(
                    {
                        "payment_ref": trx["payment_ref"],
                        "transaction_type": trx["transaction_type"],
                    }
                )
        # resequence data
        lines = sorted(bank_statement.line_ids, key=lambda x: x.date)
        for _id, line in enumerate(lines, start=1):
            line.sequence = _id
        bank_statement._compute_ending_balance()
        bank_statement.balance_end_real = bank_statement.balance_end
        bank_statement.button_post()
        transaction_in_db = self.get_transaction_import_preview(bank_statement)
        try:
            if dryrun:
                self._cr.execute(
                    "ROLLBACK TO SAVEPOINT account_bank_statement_line_import"
                )
            else:
                self._cr.execute("RELEASE SAVEPOINT account_bank_statement_line_import")
        except psycopg2.InternalError:
            pass

        return transaction_in_db

    ###################
    # BANK STATEMENT IMPORT
    ###################
    def execute_merge_bank_stmt_acc(self, dryrun=False):
        """test and check whether bank statement line we import can fillup all gaps that we detect

        # column order
        +------------+------------------+-------+-----------+-------------+------+
        | DATE       | TRANSACTION_TYPE | DEBIT | CREDIT    | BALANCE     | NOTE |
        +------------+------------------+-------+-----------+-------------+------+
        | 01/01/1970 | Auto Transfer    | 0     | 3,600,000 | 100,000,000 | CK   |
        +------------+------------------+-------+-----------+-------------+------+
        |            |                  |       |           |             |      |
        +------------+------------------+-------+-----------+-------------+------+
        |            |                  |       |           |             |      |
        +------------+------------------+-------+-----------+-------------+------+

        Algorithm:
        - we have balance_start, balance_end of csv file
        - we know groupby policy of current journal

        first sort transaction of csv file to correct order
        """

        # base option for csv import
        options = {"quoting": '"', "encoding": "utf-8-sig"}
        transactions = []
        csv_data = base64.b64decode(self.upload_file)
        cnt, content = self._read_csv(csv_data, options)
        # convert to dict
        content_dict = self.convert_to_dict(content, options)
        # tracing transaction and make a path of transaction base on balance/credit/debit
        transaction_path = self.get_transaction_path(content_dict)
        transaction_path_filter = (
            self.filter_transaction_by_bank_statement_creation_groupby(transaction_path)
        )
        bank_statement = self.get_bank_statement()
        # always trust the order we have from this transaction_path since it is data
        # from bank, dont have any reasons to doubt about this :D
        # but we may still have not enough transactions (user export data not enough)
        # and our sms service also receive transaction earlier
        # so this will be a merging between uploaded file and sms transactions

        transaction_in_statement = bank_statement.line_ids
        transaction_in_statement_correction = []

        # check who have first transacion and last transaction
        first_from = "import"
        transaction_in_statement_1st = transaction_in_statement[0]
        transaction_path_filter_1st = transaction_path_filter[0]

        if transaction_in_statement_1st["date"] < transaction_path_filter_1st["date"]:
            first_from = "odoo"
        elif transaction_in_statement_1st["date"] > transaction_path_filter_1st["date"]:
            first_from = "import"
        else:
            if (
                transaction_in_statement_1st["amount"]
                == transaction_path_filter_1st["amount"]
            ) and (
                transaction_in_statement_1st["balance"]
                == transaction_path_filter_1st["balance"]
            ):
                first_from = "odoo+import"
            elif (
                transaction_in_statement_1st["previous_balance"]
                == transaction_path_filter_1st["balance"]
            ):
                first_from = "import"
            elif (
                transaction_in_statement_1st["previous_balance"]
                == transaction_in_statement_1st["balance"]
            ):
                first_from = "odoo"
            else:
                first_from = "import"
                # TODO: need to improve how to get 1st transaction to start tracing
                # raise ValidationError(
                #     "Cannot detect first transaction to trace to import"
                # )

        sequence = 0
        if first_from == "odoo":
            transaction_in_statement_correction.append(
                (sequence, transaction_in_statement_1st, None)
            )
            picked_ids_from_import = []
            picked_ids_from_odoo = [0]
        elif first_from == "odoo+import":
            transaction_in_statement_correction.append(
                (sequence, transaction_in_statement_1st, transaction_path_filter_1st)
            )
            picked_ids_from_import = [0]
            picked_ids_from_odoo = [0]
        else:
            transaction_in_statement_correction.append(
                (sequence, None, transaction_path_filter_1st)
            )
            picked_ids_from_import = [0]
            picked_ids_from_odoo = []

        def get_candidate(transaction, transaction_list, except_ids):
            for _id, trx in enumerate(transaction_list):
                if trx["date"] >= transaction["date"] and _id not in except_ids:
                    if trx["previous_balance"] == transaction["balance"]:
                        return _id, trx
            return -1, None

        def are_transactions_same_amount(trx_from_db, trx_from_import):
            if (
                trx_from_db["amount"] == trx_from_import["amount"]
                and trx_from_db["balance"] == trx_from_import["balance"]
            ):
                return True
            return False

        def get_similar_transaction(transaction, transaction_list, except_ids):
            matched_ids = []
            for _id, trx in enumerate(transaction_list):
                if (
                    trx["date"] == transaction["date"]
                    and _id not in except_ids
                    and trx["amount"] == transaction["amount"]
                ):
                    # fmt: off
                    transaction_payment_ref = re.sub("[^\w]+", "", transaction['payment_ref'])
                    candidate_payment_ref = re.sub("[^\w]+", "", trx['payment_ref'])
                    # checking similar in ref
                    if transaction_payment_ref and candidate_payment_ref and candidate_payment_ref in transaction_payment_ref:
                        matched_ids.append(_id)
                    # fmt: on
            if len(matched_ids) == 1:
                _id = matched_ids[0]
                trx = transaction_list[_id]
                return _id, trx
            return -1, None

        if first_from == "import":
            existed = transaction_in_statement_correction[-1]
            _id_odoo_similar, odoo_similar = get_similar_transaction(existed[2], transaction_in_statement, picked_ids_from_odoo)
            if _id_odoo_similar != -1:
                # re assign
                # this is exception case when first item
                picked_ids_from_odoo.append(_id_odoo_similar)
                first_from = "odoo+import"
                transaction_in_statement_correction[-1] = (existed[0], odoo_similar, existed[2])

        traverse_end_of_odoo = False
        traverse_end_of_import = False
        sequence += 1
        while True:
            (
                _seq,
                last_track_trx_odoo,
                last_track_trx_import,
            ) = transaction_in_statement_correction[-1]
            # import data is first priority
            last_track_trx = (
                last_track_trx_import if last_track_trx_import else last_track_trx_odoo
            )

            # done, pointer go through both import and odoo, and filled up the trace correctly
            # so just break and see what happens :D
            if traverse_end_of_import and traverse_end_of_odoo:
                logger.info(
                    "Reach to end of trace when import bank transaction. Looks good now"
                )
                break

            # find the next one from 2 source
            # check prev balance match with last_track_trx
            # fmt: off
            _id_import, candidate_from_import = get_candidate(last_track_trx, transaction_path_filter, picked_ids_from_import)
            _id_odoo, candidate_from_odoo = get_candidate(last_track_trx, transaction_in_statement, picked_ids_from_odoo)
            # fmt: on

            if not traverse_end_of_import and candidate_from_import:
                if candidate_from_import == transaction_path_filter[-1]:
                    traverse_end_of_import = True
            if not traverse_end_of_odoo and candidate_from_odoo:
                if candidate_from_odoo == transaction_in_statement[-1]:
                    traverse_end_of_odoo = True
            # check if all item in the picked_ids_from_odoo and picked_ids_from_import
            if set(range(len(transaction_path_filter))) == set(picked_ids_from_import):
                traverse_end_of_import = True
            if set(range(len(transaction_in_statement))) == set(picked_ids_from_import):
                traverse_end_of_odoo = True

            # if _id_import == -1 or _id_odoo == -1:
            #     print("MISS MATCH HERE")
            #     pass

            # case 1: only odoo match
            if _id_odoo != -1 and candidate_from_odoo.is_gap() == False:
                # just update info to transaction in case both import and odoo
                # has same entry
                picked_ids_from_odoo.append(_id_odoo)
                if _id_import != -1:
                    transaction_in_statement_correction.append(
                        (sequence, candidate_from_odoo, candidate_from_import)
                    )
                    picked_ids_from_import.append(_id_import)
                else:
                    transaction_in_statement_correction.append(
                        (sequence, candidate_from_odoo, None)
                    )
            # case 1: only import match
            elif _id_import != -1:
                # fmt: off
                _id_odoo_similar, odoo_similar = get_similar_transaction(candidate_from_import, transaction_in_statement, picked_ids_from_odoo)
                # fmt: on
                if _id_odoo_similar != -1:
                    # this entry is not matched balance due to sms data but it matched date/amount and have similar payment_ref -> update balance for it
                    picked_ids_from_odoo.append(_id_odoo_similar)
                picked_ids_from_import.append(_id_import)
                if _id_odoo_similar:
                    transaction_in_statement_correction.append(
                        (sequence, odoo_similar, candidate_from_import)
                    )
                else:
                    transaction_in_statement_correction.append(
                        (sequence, None, candidate_from_import)
                    )
            else:
                # if no match but GAP in odoo matches
                if _id_odoo != -1 and candidate_from_odoo.is_gap():
                    picked_ids_from_odoo.append(_id_odoo)
                    transaction_in_statement_correction.append(
                        (sequence, candidate_from_odoo, None)
                    )
                else:
                    if traverse_end_of_import:
                        logger.info(
                            "Reach to end of trace when import bank transaction. But some odoo entry is not matched."
                        )
                        break
                    raise ValidationError("Lost trace of transaction")
            # checking it reaches to end of list
            sequence += 1

        print_debug(transaction_in_statement_correction)
        # statement to unlink
        # statement to add
        stmt_to_unlink = transaction_in_statement.mapped("id")
        stmt_to_update = []
        stmt_to_add = []

        for seq, trx_odoo, trx_import in transaction_in_statement_correction:
            if trx_odoo:
                stmt_to_unlink.remove(trx_odoo.id)
                stmt_to_update.append((seq, trx_odoo, trx_import))
                continue
            if trx_import:
                stmt_to_add.append((seq, None, trx_import))

        # validate all unlink statement is not reconciled
        self._cr.execute("SAVEPOINT account_bank_statement_line_import")

        # fmt: off
        self.env["account.bank.statement.line"].browse(stmt_to_unlink).button_undo_reconciliation()
        self.env["account.bank.statement.line"].browse(stmt_to_unlink).unlink()
        # fmt: on
        for seq, stmt_odoo, data in stmt_to_update:
            update_vals = {"sequence": seq}
            if data:
                update_vals.update(
                    {
                        # specical update to correct the balance
                        "balance": data["balance"],
                        "transaction_type": data["transaction_type"],
                    }
                )
                try:
                    if not stmt_odoo.is_reconciled:
                        # try to update payment_ref
                        stmt_odoo.update({"payment_ref": data["payment_ref"]})
                except UserError:
                    pass
            stmt_odoo.update(update_vals)

        add_list = []
        for seq, _, data in stmt_to_add:
            trx = {
                "sequence": seq,
                "date": data["date"],
                "amount": data["amount"],
                "payment_ref": data["payment_ref"],
                "balance": data["balance"],
                "transaction_type": data["transaction_type"],
                "statement_id": bank_statement.id,
            }
            add_list.append(trx)
        bank_statement.write({"state": "open"})
        self.env["account.bank.statement.line"].create(add_list)
        bank_statement._compute_ending_balance()
        bank_statement.balance_end_real = bank_statement.balance_end
        bank_statement.button_post()
        transaction_in_db = self.get_transaction_import_preview(bank_statement)
        try:
            if dryrun:
                self._cr.execute(
                    "ROLLBACK TO SAVEPOINT account_bank_statement_line_import"
                )
            else:
                self._cr.execute("RELEASE SAVEPOINT account_bank_statement_line_import")
        except psycopg2.InternalError:
            pass
        return transaction_in_db
