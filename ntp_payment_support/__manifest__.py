{
    "name": "NTP Payment Support Tools",
    "category": "Accounting",
    "sequence": 55,
    "author": "NTP Team",
    "summary": "Auto Processing Payment Remittance With External Data Source Like Mail Server",
    "website": "https://ntp-tech.vn",
    "version": "1.5.1",
    "description": """

    Ver 1.0
    =======
    - First release

    Ver 1.1
    =======
    - Payment Detail 1...6 be configurable by template

    Ver 1.2
    =======
    - Change design to make payment generated in advance, so that user can see transfer content inside odoo

    Ver 1.3
    =======
    - Make transfer status matching with reconciliation with Bank Statement and Bill
    - Allow to set transfer status when download bulk transfer file

    Ver 1.4
    =======
    - Embed hashed version of transfer content when export to bulk transfer file, it will help to reconcile

    Ver 1.5
    =======
    - add reconciled status in transfer status

    """,
    "depends": ["base", "account", "hr_payroll", "ntp_bank_branch"],
    "data": [
        "data/cron.xml",
        "data/data.xml",
        "security/ir.model.access.csv",
        "views/menu.xml",
        "views/account_payment.xml",
        "views/res_partner_bank.xml",
        "views/res_partner.xml",
        "views/hr_payslip.xml",
        "views/hr_payslip_run.xml",
        "views/account_reconcile_model.xml",
        "views/account_bank_statement.xml",
        "views/transfer_content_template.xml",
        "wizard/transfer_content_export_wizard.xml",
        "wizard/transfer_content_generate_wizard.xml",
        # "views/res_config_settings.xml",
    ],
    "qweb": [],
    "demo": [],
    "installable": True,
    "application": True,
}
