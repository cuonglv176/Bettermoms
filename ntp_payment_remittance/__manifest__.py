{
    "name": "NTP Payment Remittance",
    "category": "Accounting",
    "sequence": 55,
    "author": "NTP Team",
    "summary": "Auto Processing Payment Remittance With External Data Source Like Mail Server",
    "website": "https://ntp-tech.vn",
    "version": "1.4.7",
    "description": """

    Ver 1.0
    =======
    - First release

    Ver 1.1
    =======
    - Change design and support manual import to current bank statement to fill up missing transactions reported by sms service

    Ver 1.2
    =======
    - account.bank.statement: only show button import for bank type
    - bank.sms.transaction: correct color for state and search term, group preset
    - account.bank.statement.line: support create internal transfer in tree view inside of account.bank.statement form view

    Ver 1.3
    =======
    - Support to show 'Internal Transfer' button via customizable settings in account.bank.statement.line

    Ver 1.4
    =======
    - 'Internal Transfer' button improvement
    - import final statement for credit card and debit card
    - prioritize import bank statement data over odoo data
    - fix parser html sms mail

    TO-DO:
    ======
    - Need to support preview table to see when import file is imported what changes can be applied to bank statement, it
      is reduced error from import and let user understand if it is correct transaction.

    """,
    "depends": ["base", "fetchmail", "account", "sale_management", "account_online_synchronization"],
    "data": [
        "data/cron.xml",
        "security/ir.model.access.csv",
        "wizard/import_bank_statement_lines.xml",
        "wizard/internal_transfer_create.xml",
        "views/bank_sms.xml",
        "views/bank_sms_transaction.xml",
        "views/account_payment.xml",
        "views/account_journal.xml",
        "views/account_bank_statement.xml",
        "views/res_config_settings.xml",
    ],
    "qweb": [],
    "demo": [],
    "installable": True,
    "application": True,
}
