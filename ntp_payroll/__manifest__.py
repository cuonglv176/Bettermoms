{
    "name": "NTP PayRoll",
    "category": "Payroll",
    "summary": "Vn Payroll",
    "description": """
        Introduction
        ============

        Version 1.0
        ===========

        TO DO
        =====
        Salary rule

        - add partner into the rule to config
        - when payroll confirms will add partner from rule config to journal entry
        - when confirming journal entry, can create the bill with partner config
        
        payroll batch
        
        - need to display the all journal entries to batch
        - create journal entry with ref = batch name
        - can create the bill to employees from batch
        - bill from the employee is hidden, only can display for accountant
        - payment from employee bills also display only for accountant
        
        employee view
        
        - save payment history under employee view
        - from employee→ click payslip → need to add graph view


    """,
    "version": "1.2",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["base", "hr_payroll_account"],
    "data": [
        # "data/cron.xml",
        'views/hr_payroll_account_views.xml',
        'views/hr_employee.xml',
        'views/account_move.xml',
        'wizard/payroll_account_wizard.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
    ],
    "demo": [],
    "installable": True,
    "application": True,
}
