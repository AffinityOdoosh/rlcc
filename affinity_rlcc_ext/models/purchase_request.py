from odoo import fields, models


class PurchaseRequestInherit(models.Model):
    _inherit = 'purchase.request'

    department_id = fields.Many2one(comodel_name='hr.department', string='Department', tracking=True, index=True)
