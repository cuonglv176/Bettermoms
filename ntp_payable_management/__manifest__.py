{
    "name": "NTP Payable Management",
    "category": "Accounting",
    "sequence": 55,
    "author": "NTP Team",
    "summary": "Payment Scoring and Manage",
    "website": "https://ntp-tech.vn",
    "version": "1.9.4",
    "description": """

    Ver 1.0
    =======
    - First release

    Ver 1.3
    =======

    - Planning with payment

    Ver 1.6
    =======

    - Pop up payment when we post a bill
    - Payment undefined should be in a week
    - Transfer status in filter
    - Incorrect column in monthly view

    Ver 1.7
    =======

    - Update bank account after payment is created

    Ver 1.8, 1.9
    ============

    - Set deault payment draft when post bill
    - show amount in company currency for payment kanban view
    - default_order="amount_total_signed desc"
    - add reconciled status in transfer status

    """,
    "depends": ["base", "account", "ntp_payment_support"],
    "data": [
        "data/cron.xml",
        "data/default_config.xml",
        "security/ir.model.access.csv",
        "views/account_payment.xml",
        "views/account_payment_plan_week_views.xml",
        "views/menu.xml",
        "reports/search_template_view.xml",
        "reports/cash_flow_report.xml",
        "views/account_move.xml",
        # "views/res_partner_bank.xml",
        # "views/res_partner.xml",
        # "views/hr_payslip.xml",
        # "views/hr_payslip_run.xml",
        "wizard/account_payment_register.xml",
        "wizard/account_payment_update_bank.xml",
        # "wizard/transfer_content_generate_wizard.xml",
        "views/res_config_settings.xml",
    ],
    "assets": {
        "web.assets_qweb": [
            "ntp_payable_management/static/src/xml/*.xml",
        ],
        "web.assets_backend": [
            "ntp_payable_management/static/src/js/plan/*",
            "ntp_payable_management/static/src/js/tree_view_button_plan_create.js",
            "ntp_payable_management/static/src/scss/kanban.scss",
        ],
    },
    "qweb": [],
    "demo": [],
    "installable": True,
    "application": True,
}
