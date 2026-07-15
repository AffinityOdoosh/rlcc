from odoo import fields, models


class AccountJournalInherit(models.Model):
    _inherit = 'account.journal'

    is_miscellaneous_journal = fields.Boolean(string='Is Miscellaneous Journal')
