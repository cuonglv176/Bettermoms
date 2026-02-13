# -*- coding: utf-8 -*-
{
    "name": "NTP Invoice Collector",
    "category": "Accounting",
    "summary": "Automated Invoice Collection from Grab and Shopee with Bizzi Integration",
    "description": "Auto-fetch invoices from Grab and Shopee via API, validate against Odoo records, push to Bizzi for VAT verification.",
    "version": "15.0.1.0.0",
    "author": "NTP",
    "website": "",
    "depends": ["sale", "account", "mail", "ntp_marketplace_order"],
    "data": [
        "security/ir.model.access.csv",
        "views/collector_config.xml",
        "views/collected_invoice.xml",
        "views/res_config_settings.xml",
        "views/menu.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "OPL-1",
}
