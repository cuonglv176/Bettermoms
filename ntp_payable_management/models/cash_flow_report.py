import calendar
from random import randint
from typing import Callable, Literal, Optional
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta


from ..utils.get_report_data import build_balance_options


class CashFlowReport(models.AbstractModel):
    _inherit = "account.report"
    _name = "account.cash.flow.report"
    _description = "Cash Flow Forcast"

    filter_date = {"mode": "range", "filter": "this_month"}
    filter_show_interval = None
    # built-in
    filter_all_entries = False
    filter_journals = True

    def _get_options(self, previous_options=None):
        options = super()._get_options(previous_options)
        if options["show_interval"] == "week":
            _date_from = datetime.strptime(options["date"]["date_from"], "%Y-%m-%d")
            _date_to = datetime.strptime(options["date"]["date_to"], "%Y-%m-%d")
            _date_from = _date_from - timedelta(days=_date_from.weekday())
            _date_to = _date_to - timedelta(days=_date_to.weekday()) + timedelta(days=6)
            options["date"] = self._get_dates_period(
                options,
                _date_from,
                _date_to,
                options["date"]["mode"],
                period_type=options["date"]["period_type"],
                strict_range=options["date"]["strict_range"],
            )
        elif options["show_interval"] in ["month", "quarter", "year"]:
            _date_from = datetime.strptime(options["date"]["date_from"], "%Y-%m-%d")
            _date_to = datetime.strptime(options["date"]["date_to"], "%Y-%m-%d")
            _date_from = _date_from.replace(day=1)
            _date_to = _date_to.replace(day=1) + relativedelta(months=1, days=-1)
            options["date"] = self._get_dates_period(
                options,
                _date_from,
                _date_to,
                options["date"]["mode"],
                period_type=options["date"]["period_type"],
                strict_range=options["date"]["strict_range"],
            )
        return options

    @api.model
    def _generate_interval(self, options, sort_func: Optional[Callable] = None):
        # TODO: need to gen dynamic column here
        _today = fields.Date.today()
        _date_from = datetime.strptime(options["date"]["date_from"], "%Y-%m-%d")
        _date_to = datetime.strptime(options["date"]["date_to"], "%Y-%m-%d")
        show_interval = options["show_interval"]

        def get_suffix_from_time(s_date: date, type: Literal["month", "week"]):
            if type == "week":
                if _today.isocalendar()[1] < s_date.isocalendar()[1]:
                    return "(F)"
            if type == "month":
                if _today.month < s_date.month:
                    return "(F)"
            return "(A)"

        def build_week_interval():
            _data = []
            _start_date = _date_from
            while _start_date <= _date_to:
                _end_date = _start_date + timedelta(days=6)
                _week_no = _start_date.strftime("%Y-W%V")
                _start_str = _start_date.strftime("%a %Y-%m-%d")
                _end_str = _end_date.strftime("%a %Y-%m-%d")
                _suffix = get_suffix_from_time(_start_date, "week")
                _data.append(
                    {
                        "balance_start_date": _start_date,
                        "balance_end_date": _end_date,
                        "display": f"{_week_no} {_suffix}",
                        "title": f"{_week_no}: {_start_str} -> {_end_str}",
                    }
                )
                # start a new week
                _start_date += timedelta(days=7)
            return _data

        def build_month_interval():
            _data = []
            _start_date = _date_from + timedelta(
                days=-_date_from.day + 1
            )  # 1st of Month
            while _start_date <= _date_to:
                _days_in_month = calendar.monthrange(
                    _start_date.year, _start_date.month
                )[1]
                # end of Month
                _end_date = _start_date + timedelta(days=_days_in_month - 1)
                _month_no = _start_date.strftime("%Y-%b")
                _start_str = _start_date.strftime("%Y-%m-%d")
                _end_str = _end_date.strftime("%Y-%m-%d")
                _suffix = get_suffix_from_time(_start_date, "month")
                _data.append(
                    {
                        "balance_start_date": _start_date,
                        "balance_end_date": _end_date,
                        "display": f"{_month_no} {_suffix}",
                        "title": f"{_month_no}: {_start_str} -> {_end_str}",
                    }
                )
                # start a new month
                _start_date = _end_date + timedelta(days=1)
            return _data

        data = []
        if show_interval == "week":
            # date_from - date_from+6, date_from+7 - date_from+13, ...
            data = build_week_interval()
        elif show_interval == "month":
            # date_from - end Month #1, 01 Month#2 - end Month#2, ...
            data = build_month_interval()
        elif show_interval == "quarter":
            # TODO: date_from - end Q#1, 1st date Q#2 - end Q#2, ...
            data = build_month_interval()
        elif show_interval == "year":
            # TODO: date_from Year#1 - 31 Dec Year#1, 01 Year#2 - end Year#2, ...
            data = build_month_interval()
        else:
            raise UserError("not support this interval value")
        return data

    @api.model
    def _get_templates(self):
        templates = super(CashFlowReport, self)._get_templates()
        templates["line_template"] = "ntp_payable_management.line_cash_flow_template"
        templates[
            "search_template"
        ] = "ntp_payable_management.search_template_cash_flow_report"
        return templates

    @api.model
    def _get_columns_name(self, options):
        intervals = self._generate_interval(options)
        # by week, month, quarter, year
        columns_names = [
            {"name": "Data"},
        ]
        for intv in intervals:
            columns_names.append(
                {
                    "name": intv["display"],
                    "title": intv["title"],
                    "class": "number",
                    "data-toggle": intv["title"],
                }
            )
        return columns_names

    @api.model
    def _get_report_name(self):
        return _("Cash Flow Forcast")

    def _init_filter_show_interval(self, options, previous_options=None):
        options["available_show_intervals"] = [
            {"name": "Weekly", "id": "week"},
            {"name": "Monthly", "id": "month"},
            {"name": "Quarterly", "id": "quarter"},
            {"name": "Yearly", "id": "year"},
        ]
        if previous_options and "show_interval" in previous_options:
            options["show_interval"] = previous_options["show_interval"]
        else:
            options["show_interval"] = "week"

        # TODO: options should be change automatically when date_filter change to month, quarter, year or specific range

    @api.model
    def _get_balance_from_balance_sheet_report(self, options, at_date: date):
        options_balance_sheet_report = build_balance_options(options, at_date)
        default_bs = self.env.ref(
            "account_reports.account_financial_report_balancesheet0"
        )
        headers, lines = default_bs._get_table(options_balance_sheet_report)
        try:
            value = [x for x in lines if x["name"] == "Bank and Cash Accounts"][0][
                "columns"
            ][0]["no_format"]
        except Exception as e:
            value = 0
        return value

    @api.model
    def _get_cash_out_data(self, options, from_date: date, to_date: date):
        query = """
SELECT 
	ap.id AS id,
	ap_move.ref AS ref
FROM account_payment ap
JOIN account_move ap_move ON ap_move.id = ap.move_id
WHERE 
	ap.payment_type = 'outbound'
	AND ap.partner_type = 'supplier'
	AND ap_move.state = 'posted'
	AND date >= %s
	AND date <= %s
;
        """
        params = from_date.strftime("%Y-%m-%d"), to_date.strftime("%Y-%m-%d")
        self.env.cr.execute(query, params)
        data = self._cr.dictfetchall()
        amount = 0
        entries = self.env["account.payment"].browse([x["id"] for x in data])
        for entry in entries:
            amount += entry.amount_company_currency_signed
        return amount

    @api.model
    def _get_lines(self, options, line_id=None):
        fake_data = lambda: randint(10, 100) * randint(10000, 100000) or 0
        format_value = lambda value: self.format_value(value, blank_if_zero=True)
        intervals = self._generate_interval(options)

        def get_balance_start_date(options, intv):
            return self._get_balance_from_balance_sheet_report(
                options, intv["balance_start_date"]
            )

        def get_balance_end_date(options, intv):
            return self._get_balance_from_balance_sheet_report(
                options, intv["balance_end_date"]
            )

        def get_cash_out_data(options, intv):
            return self._get_cash_out_data(
                options,
                from_date=intv["balance_start_date"],
                to_date=intv["balance_end_date"],
            )

        def get_cash_in_data(options, intv):
            return 0

        def get_cash_out_data_forcast(options, intv):
            if options["show_interval"] == "month":
                record = self.env["account.payment.plan.month"].search(
                    [
                        ("target_date", ">=", intv["balance_start_date"]),
                        ("target_date", "<=", intv["balance_end_date"]),
                    ]
                )
                if record:
                    return record.budget_out
            elif options["show_interval"] == "week":
                record = self.env["account.payment.plan.week"].search(
                    [
                        ("target_date", ">=", intv["balance_start_date"]),
                        ("target_date", "<=", intv["balance_end_date"]),
                    ]
                )
                if record:
                    return record.budget_out
            return 0

        def get_cash_in_data_forcast(options, intv):
            if options["show_interval"] == "month":
                record = self.env["account.payment.plan.month"].search(
                    [
                        ("target_date", ">=", intv["balance_start_date"]),
                        ("target_date", "<=", intv["balance_end_date"]),
                    ]
                )
                if record:
                    return record.budget_in
            elif options["show_interval"] == "week":
                record = self.env["account.payment.plan.week"].search(
                    [
                        ("target_date", ">=", intv["balance_start_date"]),
                        ("target_date", "<=", intv["balance_end_date"]),
                    ]
                )
                if record:
                    return record.budget_in
            return 0

        BEGINNING_BALANCE = "Beginning Balance"
        CASH_IN_FLOW = "Cash IN Flow"
        CASH_OUT_FLOW = "Cash OUT Flow"
        CASH_IN_FLOW_FORCAST = "Cash IN Flow (Forcast)"
        CASH_OUT_FLOW_BUDGET = "Cash OUT Flow (Budget)"
        ENDING_BALANCE = "Beginning Balance"

        _map = {
            BEGINNING_BALANCE: get_balance_start_date,
            CASH_IN_FLOW: get_cash_in_data,
            CASH_OUT_FLOW: get_cash_out_data,
            CASH_IN_FLOW_FORCAST: get_cash_in_data_forcast,
            CASH_OUT_FLOW_BUDGET: get_cash_out_data_forcast,
            ENDING_BALANCE: get_balance_end_date,
        }

        data = []
        for order, row_key in enumerate(
            [
                BEGINNING_BALANCE,
                CASH_IN_FLOW,
                CASH_IN_FLOW_FORCAST,
                CASH_OUT_FLOW,
                CASH_OUT_FLOW_BUDGET,
                ENDING_BALANCE,
            ]
        ):
            row = {
                "id": order,
                "columns": [
                    {"name": row_key},
                ],
                "level": 1,
            }
            for _, intv in enumerate(intervals):
                if row_key in _map:
                    value = _map[row_key](options, intv)
                else:
                    raise UserError("wrong dataset")
                row["columns"].append(
                    {
                        "name": f"{(format_value(value))}",
                        "class": "number",
                        "no_format": value,
                    },
                )
            data.append(row)
        return data + [
            {
                "id": "grand_total",
                "name": "Total",
                "level": 1,
                "columns": [
                    {"name": ""},
                    # TODO: calculate total data here
                ],
            },
        ]
