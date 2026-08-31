# -*- coding: utf-8 -*-

{
    'name': 'Affinity Report XLSX',
    'author': 'Affinity Business Suite',
    'website': 'https://affinitysuite.net',
    'support': 'info@affinitysuite.net',
    'category': 'Reporting',
    'summary': 'Affinity Report XLSX Module',
    'description': '''Affinity Report XLSX Module''',
    'version': '18.0',
    'depends': [],
    'external_dependencies': {'python': ['xlsxwriter', 'xlrd']},
    'data': [],
    'assets': {
        'web.assets_backend': [
            'affinity_report_xlsx/static/src/js/report/action_manager_report.esm.js',
        ],
    },
    'images': [],
    'price': 4000000,
    'currency': 'EUR',
    'license': 'OPL-1',
    'application': False,
    'auto_install': False,
    'installable': True,
}
