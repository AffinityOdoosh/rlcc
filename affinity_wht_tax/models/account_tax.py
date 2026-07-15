from odoo import models, fields


class AccountTaxInherit(models.Model):
    _inherit = 'account.tax'

    tax_type = fields.Selection(selection=[
        ('standard', 'Standard'),
        ('with_sales', 'With Sales Tax'),
        ('on_sales', 'On Sales Tax'),
    ], string='Withholding Type', default='standard', required=True)
    type_tax_use = fields.Selection(selection_add=[
        ('withholding', 'Withholding'),
    ], ondelete={'withholding': 'set default'})
