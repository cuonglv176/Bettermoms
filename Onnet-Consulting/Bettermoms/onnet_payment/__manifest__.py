{
    'name': 'Onnet Receipts / Payslip',
    'summary': """Receipts / Payslip """,

    'description': """
        Receipts / Payslip
    """,
    'author': "Onnet",
    'website': "",
    'category': 'account',
    'version': '1.0',
    'depends': ['base', 'account', 'account_accountant'],
    'images': [
        'static/description/icon.png',
    ],
    'data': [
        'views/payment_phieu_thu.xml',
        'views/payment_phieu_chi.xml',
        'views/payment_giay_bao_no.xml',
        'views/payment_giay_bao_co.xml',
        'views/account_journal_form_view.xml',
        'report/phieu_thu_chi.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
