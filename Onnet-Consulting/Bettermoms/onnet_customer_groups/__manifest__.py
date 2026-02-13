# -*- coding: utf-8 -*-
{
    'name': "Onnet - Customer Groups",

    'depends': ['base', 'coupon',
                'account'],

    'sequence': 31,

    'category': 'base',

    'summary': "Base Groups",
    'author': "Onnet",
    'website': "https://on.net.vn",
    'version': '0.1',

    # always loaded
    'data': [
        'views/res_partner.xml',
    ],

    'qweb': [
    ],

    'installable': True,
    'application': True,
}
