from odoo import models, fields


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    voucher_date_from = fields.Date(string='Voucher Date From', copy=False, index=True)
    voucher_date_to = fields.Date(string='Voucher Date To', copy=False, index=True)
