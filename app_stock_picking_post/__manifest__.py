# -*- coding: utf-8 -*-

# Created on 20120-01-05
# author: 广州尚鹏，https://www.sunpop.cn
# email: 300883@qq.com
# resource of Sunpop
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Odoo12在线用户手册（长期更新）
# https://www.sunpop.cn/documentation/user/12.0/zh_CN/index.html

# Odoo12在线开发者手册（长期更新）
# https://www.sunpop.cn/documentation/12.0/index.html

# Odoo10在线中文用户手册（长期更新）
# https://www.sunpop.cn/documentation/user/10.0/zh_CN/index.html

# Odoo10离线中文用户手册下载
# https://www.sunpop.cn/odoo10_user_manual_document_offline/
# Odoo10离线开发手册下载-含python教程，jquery参考，Jinja2模板，PostgresSQL参考（odoo开发必备）
# https://www.sunpop.cn/odoo10_developer_document_offline/

##############################################################################
#    Copyright (C) 2009-TODAY Sunpop.cn Ltd. https://www.sunpop.cn
#    Author: Ivan Deng，300883@qq.com
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#    See <http://www.gnu.org/licenses/>.
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

{
    'name': "Customize Effective Date for Stock transfer picking, Post done stock operation. 库存滞后录单",
    'version': '14.21.02.05',
    'author': 'Sunpop.cn',
    'category': 'Base',
    'website': 'https://www.sunpop.cn',
    'license': 'LGPL-3',
    'sequence': 2,
    'price': 38.00,
    'currency': 'EUR',
    'images': ['static/description/banner.png'],
    'depends': [
        'stock',
    ],
    'summary': '''
    Stock transfer post done. done in past. stock operation post done. Set Effective Date in past.
    Date of Transfer can input past date. set Date of Transfer before. 
    Input stock operation history. Input stock transfer history.    
    ''',
    'description': '''    
    Support Odoo 14, 13，12, Enterprise and Community Edition
    1. Customize Set Effective Date	 of Transfer in stock transfer.
    2. Auto set now for Effective Date of Transfer done. user can modify the date done(Date of Transfer)
    3. Restrict Date of Transfer can not bigger than today.
    4. Set stock move in past day , set product move in past day
    5. Multi-language Support.
    6. Multi-Company Support.
    7. Support Odoo 14,13,12, Enterprise and Community Edition
    ==========
    1. 可配置仓库作业的生效日期。
    2. 仓库作业的生效日期自动设置为当前时间，可调整为过去的时间。
    3. 仓库作为不可以设置为未来的时间。
    4. 仓库作业产生的库存移动，产品移动也同时按设置的时间生成，即可设置为历史时间。
    5. 多语言支持
    6. 多公司支持
    7. Odoo 14. 13, 12, 企业版，社区版，多版本支持
    ''',
    'data': [
        'views/stock_picking_views.xml',
    ],
    'qweb': [
        # 'static/src/xml/*.xml',
    ],
    'demo': [],
    # 'pre_init_hook': 'pre_init_hook',
    # 'post_init_hook': 'post_init_hook',
    # 'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
