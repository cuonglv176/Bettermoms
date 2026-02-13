# -*- coding: utf-8 -*-
{
    'name': """
        Auto fill company info
    """,
    'summary': """
        Auto fill company info from Vietnam tax id
       """,
    'description': """
        Auto fill company info from Vietnam tax id
    """,
    'author': "hoangminh248@gmail.com",
    'website': "",
    'images': ['static/description/tax_vn.png'],
    'category': 'Accounting/Accounting',
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/res_partner.xml'
    ],

    "assets": {
        "web.assets_qweb": [
            "autofill_company_vietnam_taxid/static/src/xml/tree_view_button_update_partner.xml",
        ],
        "web.assets_backend": [
            "autofill_company_vietnam_taxid/static/src/js/tree_view_update_partner.js",
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
