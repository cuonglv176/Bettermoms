{
    "name": "NTP FCT CIT Report",
    "category": "Accounting/Tax",
    "description": """
        Customize VN Accounting Tax Report
        Version 1.1
        ===========

        TO DO
        =====
        Start create report with sql, export xlsx
        
        Version 1.2
        ===========

        TO DO
        =====
        create data by xml
        Version 1.3
        ===========

        TO DO
        =====
        create model for fct business model and link to excel to display
        
        
    """,
    "version": "1.3",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["base", "account_reports"],
    "data": [
        "security/ir.model.access.csv",
        "reports/fct_cit_report.xml",
        "views/fct_business_line.xml",
        "views/data.xml",
        "views/res_company.xml",
        "views/account_account.xml",
        "views/fct_report_data.xml",
    ],

    "demo": [],
    "installable": True,
    "application": True,
}
