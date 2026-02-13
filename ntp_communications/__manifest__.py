{
    "name": "NTP Communications",
    "category": "Sales",
    "summary": "Communications Between Users/Groups",
    "description": """
        Introduction
        ============

        Support comments and notes for users/groups base on some events

        Version 1.0
        ===========

        TO DO
        =====


    """,
    "version": "1.0",
    "author": "Duy Chu",
    "website": "",
    "description": "",
    "depends": ["base", "account", "sale_management", "sale_stock", "stock"],
    "data": [
        "views/stock_picking_views.xml",
        "views/sale_order_views.xml",
        "views/res_config_settings.xml",
        # "security/ir.model.access.csv",
        # "views/res_partner.xml",
        # "wizard/sale_make_invoice_advance.xml",
        # "views/so_to_sliced_invoice.xml",
        # "data/cron.xml",
        # "views/menu.xml",
        # "views/einvoice.xml",
        # "views/res_company.xml",
        # "views/product_product.xml",
        # "wizard/einvoice_sync_from_odoo.xml",
        # "wizard/einvoice_sync_from_provider.xml",
        # "wizard/einvoice_create.xml",
    ],
    "assets": {
        # "web.assets_qweb": [
        #     "ntp_communications/static/src/xml/*.xml",
        # ],
        # "web.assets_backend": [
        #     "ntp_communications/static/src/js/notify_create_invoice_from_stock_picking_done.xml.js",
        # ],
    },
    "demo": [],
    "installable": True,
    "application": True,
}
