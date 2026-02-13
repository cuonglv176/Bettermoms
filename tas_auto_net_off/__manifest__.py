{
    'name': 'Auto netoff',
    'summary': """Auto netoff """,

    'description': """
        Auto netoff
    """,
    'author': "TASYS",
    'website': "",
    'category': 'tasys',
    'version': '1.0',
    'depends': ['base',  'account'],
    'images': [
        'static/description/icon.png',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_netoff.xml',
        'views/account_account.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
