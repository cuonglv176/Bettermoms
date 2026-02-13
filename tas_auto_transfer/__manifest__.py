{
    'name': 'Auto transfer',
    'summary': """Auto transfer """,

    'description': """
        Auto transfer
    """,
    'author': "TASYS",
    'website': "",
    'category': 'tasys',
    'version': '1.0',
    'depends': ['base',  'account', 'l10n_vn_tasys'],
    'images': [
        'static/description/icon.png',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_transfer.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
