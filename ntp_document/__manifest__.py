{
    "name": "NTP Document Upload",
    "category": "Document",
    "description": """
        Customize Document upload and store at Document module
        
        Version 1.1
        ===========

        TO DO
        =====
        make function to store document to Document Module

        
    """,
    "version": "1.1",
    "author": "BinhTT",
    "website": "",
    "description": "",
    "depends": ["mail", "documents"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/document_existed_update.xml",
        "views/document_folder.xml",
    ],

    "demo": [],
    "installable": True,
    "application": True,
}
