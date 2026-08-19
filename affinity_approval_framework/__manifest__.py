# -*- coding: utf-8 -*-

{
    'name': 'Approval Framework',
    'author': 'Hasnan Saleem',
    'website': '',
    'support': 'hasnansaleem07000@gmail.com',
    'category': 'Approval',
    'summary': 'Approval Framework Module',
    'description': '''Approval Framework Module''',
    'version': '18.0',
    'depends': ['mail'],
    'data': [
        'data/ir_cron.xml',
        'data/main_activity_type.xml',
        'data/main_message_subtype.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'report/tier_validation_templates.xml',
        'views/res_config_settings_views.xml',
        'views/tier_definition_view.xml',
        'views/tier_review_view.xml',
        'views/tier_validation_exception_view.xml',
        'wizard/comment_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'affinity_approval_framework/static/src/components/**/*',
            'affinity_approval_framework/static/src/js/**/*',
        ],
    },
    'images': [],
    'price': 4000000,
    'currency': 'EUR',
    'license': 'OPL-1',
    'application': True,
    'auto_install': False,
    'installable': True,
}
