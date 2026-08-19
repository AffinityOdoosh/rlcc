# -*- coding: utf-8 -*-

{
    'name': 'Affinity Record Expense Approval',
    'author': 'Affinity Business Suite',
    'website': 'https://affinitysuite.net',
    'support': 'info@affinitysuite.net',
    'category': 'Expense',
    'summary': 'Affinity Record Expense Approval Module',
    'description': '''Affinity Record Expense Approval Module''',
    'version': '18.0',
    'depends': ['affinity_record_expense', 'affinity_approval_framework'],
    'data': [
        'data/mail_data.xml',
        # 'views/record_expense_views.xml',
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
