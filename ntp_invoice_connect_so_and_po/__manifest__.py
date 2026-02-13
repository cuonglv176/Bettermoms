{
    "name": "NTP Invoice Connect SO and PO",
    "category": "Accounting",
    "summary": "Invoice Connect SO and PO Ones",
    "description": """
        Introduction
        ============

        Support connect  sale order and purchase from invoices 

        Version 1.1
        ===========

        TO DO
        =====
        Start create field and function to update from sale and purchase
        
        
        Version 1.2
        ===========

        TO DO
        =====
        make field sale_id and purchase_order_id is not readonly at draft state
        
        
        Version 1.3
        ===========

        TO DO
        =====
        - add invoice manual update SO and PO can open via SO and PO form
        - add purchase Subscription can manual update at invoice
        - add function can open invoice purchase subscription form
        
        Version 1.4
        ===========

        TO DO
        =====
        - move the field display at 'other info' tab
    """,
    "version": "1.4",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["base", "account", "sale_management", "purchase"],
    "data": ['views/account_move_invoice.xml'
        ],
    "demo": [],
    "installable": True,
    "application": True,
}
