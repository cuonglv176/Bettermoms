# -*- coding: utf-8 -*-
{
    "name": "NTP Invoice Collector",
    "category": "Accounting",
    "summary": "Automated Invoice Collection from Grab, Shopee, SPV Tracuuhoadon, and Shinhan Bank with Bizzi Integration",
    "description": (
        "Auto-fetch invoices from Grab (vn.einvoice.grab.com), Shopee, "
        "SPV Tracuuhoadon (spv.tracuuhoadon.online), and Shinhan Bank eInvoice "
        "(einvoice.shinhan.com.vn) via session/JWT-based authentication with "
        "auto-CAPTCHA solving (OpenAI Vision API). Validate against Odoo records "
        "and push to Bizzi for VAT verification."
    ),
    "version": "15.0.2.0.0",
    "author": "NTP",
    "website": "",
    "depends": ["sale", "account", "mail", "ntp_marketplace_order"],
    "data": [
        "security/ir.model.access.csv",
        "views/collector_config.xml",
        "views/collected_invoice.xml",
        "views/res_config_settings.xml",
        "views/collector_log.xml",
        "views/menu.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "OPL-1",
}
