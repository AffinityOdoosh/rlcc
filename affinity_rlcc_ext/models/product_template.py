from odoo import models, fields


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    existing_code = fields.Char(string='Existing Code', help='Code from the previous company')
    old_existing_code = fields.Char(string='Old Existing Code')
    old_existing_name = fields.Char(string='Old Existing Name')

