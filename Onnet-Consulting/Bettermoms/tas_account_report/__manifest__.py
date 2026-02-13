{
    'name': 'Enterprise account report',
    'summary': """Enterprise account report """,

    'description': """
        Tas account report
    """,
    'author': "TASYS",
    'website': "",
    'category': 'tasys',
    'version': '1.0',
    'depends': ['base',  'account', 'account_reports'],
    'images': [
        'static/description/icon.png',
    ],
    'data': [
        'views/account_account.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
