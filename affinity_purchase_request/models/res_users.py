from odoo import models, fields


class ResUsersInherit(models.Model):
    _inherit = 'res.users'

    location_id = fields.Many2one(comodel_name='stock.location', string='Location', domain="[('usage','=','internal')]")
