from odoo import models, fields


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    existing_code = fields.Char(string='Existing Code', help='Code from the previous company')
