{
    'name': "E-Invoice",

    'summary': """
            E-Invoice Intergration
        """,

    'description': """
        E-Invoice Intergration
    """,
    "data": [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/data.xml',
        'view/invoice_viettel.xml',
        'view/account_move.xml',
        'view/res_partner.xml',
        'view/company_branch_views.xml',
        'view/res_users.xml',
    ],
    "license": "LGPL-3",
    "depends": ['account'],
    'author': "Onnet",
    'category': 'Accounting',
    'version': '1.0.1',
    'installable': True,
}
