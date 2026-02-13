# -- coding: utf-8 --
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2021. All rights reserved.


{
    'name': 'Manual Currency Exchange Rate',
    'version': '15.0.0.6',
    'category': 'Accounting',
    'sequence': 1,
    'summary': 'Manual currency exchange rate',
    'description': """
This module helps to manually enter currency exchange rate for Sales Order/Customer Invoice/Vendor Bills/Purchase Orders/Payments. 
    """,
    'website': 'http://technaureus.com/',
    'author': 'Technaureus Info Solutions Pvt. Ltd.',
    'depends': ['sale_management', 'purchase', 'account'],
    'sequence': 1,
    'license': 'Other proprietary',
    'price': 17.50,
    'currency': 'EUR',
    'data': [
        'views/sale_order.xml',
        'views/invoice.xml',
        'views/purchase.xml',
        'views/invoice_supplier.xml',
        'views/account_payment.xml',
        'views/stock_picking.xml'
    ],
    'demo': [],
    'css': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
