{
    'name': 'Auto separate contra account',
    'summary': """Auto separate contra account """,

    'description': """
        Auto separate contra account
    """,
    'author': "TASYS",
    'website': "",
    'category': 'tasys',
    'version': '1.0',
    'depends': ['base', 'account', 'vn_einvoice'],
    'images': [
        'static/description/icon.png',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/data.xml',
        'views/account_move_separation.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
