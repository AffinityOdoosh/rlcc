from odoo import fields, models


class StockLocationInherit(models.Model):
    _inherit = 'stock.location'

    manager_id = fields.Many2one(comodel_name='res.users', string='Location Manager')
