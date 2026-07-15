from odoo import models, fields


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    withholding_tax_ids = fields.Many2many(comodel_name='account.tax', string='Withholding Taxes',
                                          domain=[('type_tax_use', '=', 'withholding')])
