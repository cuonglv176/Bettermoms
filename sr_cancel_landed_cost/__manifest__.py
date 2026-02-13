# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

{
    "name": "Cancel Stock Landed Cost in Odoo",
    "version": "15.0.0.0",
    "category": "Inventory",
    "license": "OPL-1",
    "summary": "Cancel and Reset Stock Landed Cost in Odoo Reverse stock landed cost Recalculate stock landed cost",
    "description": """
        Cancel and Reset Stock Landed Cost in Odoo
        Reverse stock landed cost
        Recalculate stock landed cost
        Reverse and Cancel WMS Landed Costs
        Cancel Validated Landed Cost
        Recalculate Validated stock landed cost
        Stock landed cost revert
        Rectify the mistake on stock landed cost in odoo
        Landed Cost Reverse
        WMS landed cost reverse and cancel
        WMS landed cost Cancel
        Warehouse Landed Cost Cancel
        Recalculate Inventory Valuation on cancel landed Cost
        Inherit stock.landed.cost  
        Sitaram Solutions stock landed cost application on odoo
        """,
    "price": 10,
    "currency": "EUR",
    "author": "Sitaram",
    "website": "https://sitaramsolutions.in",
    "depends": ["base", "stock_landed_costs"],
    "data": [
        "views/sr_inherit_landed_cost.xml",
    ],
    "installable": True,
    "auto_install": False,
    "live_test_url": "https://youtu.be/UTc2afE_FRs",
    "images": ["static/description/banner.png"],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
