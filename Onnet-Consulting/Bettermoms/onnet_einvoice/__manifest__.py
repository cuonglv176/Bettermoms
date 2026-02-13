{
    'name': 'Onnet E-Invoice',
    'description': """
         Onnet E-Invoice
    """,
    'category': 'Accounting',
    'sequence': 33,
    "depends": ['vn_einvoice'],
    "data": [
        # Security
        'security/ir.model.access.csv',
        # Views
        'views/account_move_view.xml',
        # Wizards
        'wizards/wizard_update_move_street_view.xml',
    ],
    'version': '1.0.1',
    'installable': True,
}
