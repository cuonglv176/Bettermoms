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
        'wizard/invoice_viettel_validate_confirm.xml',
        'view/res_users.xml',
    ],
    "assets": {
        "web.assets_qweb": [
            "vn_einvoice/static/src/xml/tree_view_button_sync_s_invoice.xml",
        ],
        "web.assets_backend": [
            "vn_einvoice/static/src/js/tree_view_s_invoice.js",
        ],
    },
    "license": "LGPL-3",
    "depends": ['account', 'web'],
    'author': "Onnet",
    'category': 'Accounting',
    'version': '1.0.1',
    'installable': True,
}
