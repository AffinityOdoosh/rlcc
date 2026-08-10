from odoo import models, fields


class AccountAccount(models.Model):
    _inherit = 'account.account'

    api_account_code = fields.Char(string='API Code', index=True,
                                   help='External API account code used for synchronization.')

    _sql_constraints = [(
        'api_account_code_unique',
        'unique(api_account_code)',
        'The API Account Code must be unique across Chart of Accounts!'
    )]
