from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    code = fields.Char(
        string="Code",
        copy=False,
        index=True
    )