# -*- coding: utf-8 -*-

{
    'name': 'Affinity Payment Approval',
    'author': 'Affinity Business Suite',
    'website': 'https://affinitysuite.net',
    'support': 'info@affinitysuite.net',
    'category': 'Approval',
    'summary': 'Affinity Payment Approval Module',
    'description': '''Affinity Payment Approval Module''',
    'version': '18.0',
    'depends': ['account', 'affinity_approval_framework'],
    'data': [
        'data/mail_data.xml',
        'views/account_payment_views.xml',
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
