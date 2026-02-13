{
    "name": "NTP Bank Branches",
    "category": "Accounting",
    "sequence": 55,
    "author": "NTP Team",
    "summary": "Bank Branches Database",
    "website": "https://ntp-tech.vn",
    "version": "1.0",
    "description": """

    Ver 1.0
    =======
    - First release



    """,
    "depends": ["base", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/bank_branch.xml",
        "views/res_bank.xml",
        "views/res_partner_bank.xml",
        "views/menu.xml",
        "data/data.xml",
        # "wizard/bulk_transfer_show_download.xml",
        # "views/res_config_settings.xml",
    ],
    "qweb": [],
    "demo": [],
    "installable": True,
    "application": True,
}
