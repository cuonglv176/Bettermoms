{
    "name": "NTP VN Tax Report",
    "category": "Accounting/Tax",
    "description": """
        Customize VN Accounting Tax Report
        ver1.2:
        create tax report compare
        ver 1.5:
        add odoo amount and tax invoice amount into form view
    """,
    "version": "1.5",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["base", "account_reports", 'ntp_einvoice', 'ntp_cne'],
    "data": [
        "security/ir.model.access.csv",
        "views/account_tax_report_compare.xml",
        "views/account_tax_report_line.xml",
        "views/account_move_line.xml",
        "views/wizard_ignore_mismatch.xml",
    ],

    "demo": [],
    "installable": True,
    "application": True,
}
