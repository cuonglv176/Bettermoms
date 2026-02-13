# -*- coding: utf-8 -*-
{
    "name": "NTP Marketplace Order",
    "category": "Sales",
    "summary": "Shopee Order Reference & Mandatory Validation on Sales Orders",
    "description": "Add Order Source field to Sales Orders with mandatory Shopee Order ID validation and uniqueness check.",
    "version": "15.0.1.0.0",
    "author": "NTP",
    "website": "",
    "depends": ["sale"],
    "data": [
        "views/sale_order.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "OPL-1",
}
