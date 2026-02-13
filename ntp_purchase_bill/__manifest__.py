{
    "name": "NTP Purchase",
    "category": "Purchase",
    "description": """
        Customize Purchase Order
        ver 1.1
        =======================
        update Purchase Order with Tax Summary on PO from linked Bills
        
        ver 1.2
        =======================
        update Vat type into account tag and sum base on VAT Type
        ver 1.3
        =======================
        update landed cost to purchase order with valuation landedd cost
        ver 1.4
        =======================
        auto tick landed cost when create bill
        
    """,
    "version": "1.4.1",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["base", "purchase", 'account', 'stock_landed_costs'],
    "data": [
        "security/ir.model.access.csv",
        'views/purchase_order.xml',
        'views/data.xml',
        'views/vat_type.xml',
        'views/account_account_tag.xml',
    ],

    "demo": [],
    "installable": True,
    "application": True,
}
