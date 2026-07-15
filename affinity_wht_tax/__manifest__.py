# -*- coding: utf-8 -*-

{
    'name': 'Affinity WHT Tax',
    'author': 'Affinity Business Suite',
    'website': 'https://affinitysuite.net',
    'support': 'info@affinitysuite.net',
    'category': 'Accounting',
    'summary': 'Affinity WHT Tax Module',
    'description': '''Affinity WHT Tax Module''',
    'version': '18.0',
    'depends': ['account', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/account_tax_views.xml',
        'views/product_template_views.xml',
        'wizard/account_payment_register_views.xml',
    ],
    'assets': {},
    'images': [],
    'price': 4000000,
    'currency': 'EUR',
    'license': 'OPL-1',
    'application': False,
    'auto_install': False,
    'installable': True,
}
