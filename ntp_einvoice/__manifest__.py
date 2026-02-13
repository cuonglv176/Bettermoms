{
    "name": "NTP Electronic Invoice",
    "category": "Accounting",
    "summary": "Electronic Invoice",
    "description": """
        Introduction
        ============

        Support create einvoice from various provider

        Version 1.0
        ===========

        - First release

        Version 1.1
        ===========

        - Support create multiple e-invoices grouped by same VAT rate (follow invoice policy of VN)
        - UoM save in product for einvoice
        - Allow set invoice number manually, when api not return it (stuck at 'creating' and invoice name still '/')
        - Send Email To Customer
        - Support replace/placed_by einvoice

        Version 1.2
        ===========

        - Support pulling einvoice from sinvoice api v1
        - Note: some features will not supported by sinvoice api v1

        Version 1.3
        ===========

        - Support create einvoice with note
        - Validate company_name and tax_code if buyer_type is company

        Version 1.4
        ===========

        - Must validate invoice address when issue invoice
        - Show tax authorities code in tree view

        Version 1.5
        ===========

        - Fix address confirm einvoice

        Version 1.6,1.7
        ===============

        - Fix request,adjust invoice status
        - Fix pattern display string
        - Fix odoo invoice view in tree

        Version 1.8
        ===========

        - Show Address Confirm, can be changed via UI
        - Fix adding line number when issue einvoice
        - Fix wizard of ntp vn tax
        - button to generate agreement doc for vat change

        TO DO
        =====


    """,
    "version": "1.8.5",
    "author": "Duy Chu",
    "website": "",
    "depends": ["base", "account", "onnet_customer_groups", "ntp_vn_tax"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/menu.xml",
        "views/account_move.xml",
        "views/einvoice_template.xml",
        "views/einvoice.xml",
        "views/einvoice_line.xml",
        "views/res_company.xml",
        "views/product_product.xml",
        "wizard/einvoice_preview.xml",
        "wizard/einvoice_sync_from_odoo.xml",
        "wizard/einvoice_sync_from_provider.xml",
        "wizard/einvoice_create.xml",
        "wizard/einvoice_manual_set_invoice_no.xml",
        "wizard/einvoice_send_email.xml",
        "wizard/mst_vn_finder_wizard.xml",
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
