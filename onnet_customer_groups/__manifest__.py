# -*- coding: utf-8 -*-
{
    'name': "Onnet - Customer Groups",

    'depends': ['base', 'coupon', 'sale',
                'purchase',
                'account'],

    'sequence': 31,

    'category': 'base',

    'summary': "Base Groups",
    'author': "Onnet",
    'website': "https://on.net.vn",
    'version': '1.5',

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/company_short_name.xml',
        'views/res_partner.xml',
        'views/company_group.xml',
    ],

    'qweb': [
    ],

    'installable': True,
    'application': True,
}
