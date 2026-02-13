{
    "name": "NTP Account Asset",
    "category": "Accounting Asset",
    "description": """
        Customize Accounting Asset
        Version 1.0
        ===========
        Init function sum amount when validate bill and create asset
        Version 1.1
        ===========
        fix issue when have many tax in 1 line
    """,
    "version": "1.1",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["base", "account_asset"],
    "data": [
        'views/account_tax.xml'
    ],

    "demo": [],
    "installable": True,
    "application": True,
}
