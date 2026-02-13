{
    'name': 'NTP Sale OverDue',
    'category': 'Sale',
    'sequence': 55,
    'summary': 'Sell your products online',
    'website': 'https://ntp-tech.vn',
    'version': '1.3',
    'description': "",
    'depends': ['sale_stock', 'sale_management', 'web_widget_bokeh_chart'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order.xml',
        'views/res_partner.xml',
        # 'template.xml',
        'views/interest_rate.xml',
        'views/res_config_settings_views.xml',
    ],
    # 'qweb': [
    #     "static/src/xml/template.xml",
    # ],
    'demo': [
        'data/sale_order_demo.xml'
    ],
    "assets": {
        "web.assets_qweb": [
            "ntp_sale_overdue/static/src/xml/*.xml",
        ],
        "web.assets_backend": [
            "ntp_sale_overdue/static/src/scss/overdue.scss",
            "ntp_sale_overdue/static/src/js/overdue_payment.js",
            "ntp_sale_overdue/static/src/js/overdue_payment_dashboard.js",
        ],
    },

    'installable': True,
    'application': True,
}
