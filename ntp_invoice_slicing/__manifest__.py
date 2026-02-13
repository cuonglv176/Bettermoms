{
    "name": "NTP Invoice Slicing",
    "category": "Accounting",
    "summary": "Invoice Slicing To Multiple Ones",
    "description": """
        Introduction
        ============

        Support create multiple invoices from sale order

        Version 1.0
        ===========

        First release

        Version 1.1
        ===========

        Filter one2many field data correctly base on company_group_code
        Auto cleanup not reference entry
        Not allow user configure Invoice Slicing without quota_unit=balance at the end of slicing list

        TO DO
        =====


    """,
    "version": "1.1.1",
    "author": "Duy Chu",
    "website": "",
    "depends": ["base", "account", "sale_management", "stock", "onnet_customer_groups"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "views/sale_order.xml",
        "wizard/sale_make_invoice_advance.xml",
        "views/so_to_sliced_invoice.xml",
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
        #     "ntp_einvoice/static/src/xml/*.xml",
        # ],
        # "web.assets_backend": [
        #     "ntp_einvoice/static/src/js/tax_invoice_bill_receipt_suggestion_field.js",
        #     "ntp_einvoice/static/src/js/tree_view_button_sync_tax_invoice.js",
        # ],
    },
    "demo": [],
    "installable": True,
    "application": True,
}
