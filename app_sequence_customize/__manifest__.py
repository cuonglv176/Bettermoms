# -*- coding: utf-8 -*-

# Created on 2019-01-04
# author: 广州尚鹏，https://www.sunpop.cn
# email: 300883@qq.com
# resource of Sunpop
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Odoo12在线用户手册（长期更新）
# https://www.sunpop.cn/documentation/user/12.0/en/index.html

# Odoo12在线开发者手册（长期更新）
# https://www.sunpop.cn/documentation/12.0/index.html

# Odoo10在线中文用户手册（长期更新）
# https://www.sunpop.cn/documentation/user/10.0/zh_CN/index.html

# Odoo10离线中文用户手册下载
# https://www.sunpop.cn/odoo10_user_manual_document_offline/
# Odoo10离线开发手册下载-含python教程，jquery参考，Jinja2模板，PostgresSQL参考（odoo开发必备）
# https://www.sunpop.cn/odoo10_developer_document_offline/


{
    'name': 'Sequence by month, day, year, 日期序号器',
    'version': '15.21.11.22',
    'author': 'Sunpop.cn',
    'category': 'Base',
    'website': 'https://www.sunpop.cn',
    'license': 'LGPL-3',
    'sequence': 20,
    'summary': """
    Auto Sequence Customize the sequence interval, sequence reset by day, reset by month, reset by year. multi language support.
    sequence year, sequence month, sequence day. year sequence, month sequence, day sequence.
    """,
    'description': """
    """,
    'price': 38.00,
    'currency': 'EUR',
    'depends': [
        'base',
        # 'product',
    ],
    'images': ['static/description/banner.png'],
    'data': [
        'views/ir_sequence_views.xml'
    ],
    'qweb': [
        "static/src/xml/ztree.xml",
    ],
    'demo': [
    ],
    'test': [
    ],
    'css': [
    ],
    'js': [
    ],
    'post_load': None,
    'post_init_hook': None,
    'installable': True,
    'application': True,
    'auto_install': False,
}

