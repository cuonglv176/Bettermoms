# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Revenue Recognize',
    'description': """
    """,
    'category': 'Accounting/Accounting',
    'sequence': 32,
    "depends": ["sale", "account", "account_reports"],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account_view.xml',
        'views/account_journal_view.xml',
        'views/company_branch_view.xml',
        'views/revenue_recognize_view.xml',
        'views/revenue_recognize_log_view.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': True,
}
