{
    "name": "NTP Vn Tax",
    "category": "Accounting",
    "summary": "Vn Tax",
    "description": """
        Introduction
        ============

        Version 1.0
        ===========

        Version 1.1
        ===========

        - Fix wizard of ntp vn tax
        - 20221205: update method to manual set cookie because website not set cookie by http response header but js script

        TO DO
        =====


    """,
    "version": "1.1.2",
    "author": "Duy Chu",
    "website": "",
    "description": "",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        # "data/cron.xml",
        "wizard/mst_vn_finder_wizard.xml",
        "views/res_partner.xml",
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
