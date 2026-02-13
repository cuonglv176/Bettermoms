{
    "name": "NTP Catchup & Cashup",
    "category": "Website/Website",
    "summary": "Automation Catchup & Cashup",
    "description": """
        Introduction
        ============

        Since we are using 3rd party service from some company like bizzi or docbase, we will able to receive some tax invoices from them
        The operation will be like this
        This is our cost and expense we need to keep track

        ```
        gmail --> forward --> bizzi email --> notify to odoo about invoice --> odoo process and save to tax invoice
        ```

        Version 1.2
        ===========

        - signed date = accounting date when suggestion
        - update bill_ref if not existed or update once in bill/receipt
        - aggregate invoice to single product and accounting field
        - bill/receipt creation auto created in cron

        Version 1.3
        ===========

        - show signed_date, issued_date in tree view in bill/receipt
        - fix searching vendor by name using 'ilike'
        - fix statinfo link when click not showing tax invoice in some cases
        - create invoice with payment term getting from res.partner
        - tax.invoice: when the number is different, it need to ask again for Admin Approve

        Version 1.4
        ===========

        - auto recognize product in tax invoice by setup label matrix mapping to product
        - able to update this matrix when receive new label
        - provide ext link to see invoice
        - show issued date in form/tree of account.move
        - support in_refund in selection link

        Version 1.5
        ===========

        - change design to many2many relation with account.move
        - add more fields to show in tree view
        - fix ref string when link tax invoice

        Version 1.6,1.7
        ===============

        - fix string display

        TO DO
        =====

        - currently cron task get all invoice data from beginning so it is not optimal get, can cause server
          be slow when many invoices come
        - need to add 1 more setting to keep track of last date we get invoice,
          so we only synce from that data only

    """,
    "version": "1.7",
    "author": "Duy Chu",
    "website": "",
    "description": "",
    "depends": ["base", "account", "onnet_customer_groups"],
    "data": [
        "security/ir.model.access.csv",
        "data/default_config.xml",
        "data/cron_tasks.xml",
        "wizard/bill_receipt_create_from_tax_invoice.xml",
        "wizard/tax_invoice_validate_confirm.xml",
        "views/tax_invoice.xml",
        "views/res_partner.xml",
        "views/res_company.xml",
        "views/account_move.xml",
        "views/res_config_settings.xml",
        "views/product_product.xml",
        # "views/assets.xml",
    ],
    "assets": {
        "web.assets_qweb": [
            "ntp_cne/static/src/xml/*.xml",
        ],
        "web.assets_backend": [
            "ntp_cne/static/src/js/tax_invoice_bill_receipt_suggestion_field.js",
            "ntp_cne/static/src/js/tree_view_button_sync_tax_invoice.js",
        ],
    },
    "demo": [],
    "installable": True,
    "application": True,
}
