from odoo import models, fields


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    code = fields.Char(string="Code", copy=False, index=True)
