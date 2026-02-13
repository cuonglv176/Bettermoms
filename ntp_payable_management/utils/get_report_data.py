from datetime import date
from requests import options


def build_balance_options(cash_flow_options, date: date):

    BALANCE_SHEET_AS_OF_DAY = {
        "unfolded_lines": [],
        "allow_domestic": False,
        "fiscal_position": "all",
        "available_vat_fiscal_positions": [],
        "date": {
            "string": "-",
            "period_type": "custom",
            "mode": "single",
            "strict_range": False,
            "date_from": date.strftime("%Y-01-01"),  # first date of yeat always
            "date_to": date.strftime("%Y-%m-%d"),  # target date
            "filter": "custom",
        },
        "comparison": {
            "filter": "no_comparison",
            "number_period": 1,
            "date_from": date.strftime("%Y-01-01"),  # first date of yeat always
            "date_to": date.strftime("%Y-%m-%d"),  # target date
            "periods": [],
        },
        "all_entries": False,
        # ! integrate analytics account data
        "analytic": True,
        "analytic_accounts": [],
        "selected_analytic_account_names": [],
        "analytic_tags": [],
        "selected_analytic_tag_names": [],
        # ! integrate journal filter
        "journals": [],
        "name_journal_group": "All Journals",
        "unfold_all": False,
        "unposted_in_period": True,
        # "control_domain_missing_ids": [10, 18],
        "sorted_groupby_keys": [[0]],
    }

    # this is to copy option from cash flow to balance sheet report -> get data as of specific date
    options = BALANCE_SHEET_AS_OF_DAY
    options["journals"] = cash_flow_options["journals"]
    options["name_journal_group"] = cash_flow_options["name_journal_group"]
    options["unposted_in_period"] = cash_flow_options["unposted_in_period"]
    options["all_entries"] = cash_flow_options["all_entries"]

    return options
