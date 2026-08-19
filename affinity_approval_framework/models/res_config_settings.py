from odoo import fields, models


class ResConfigSettingsInherit(models.TransientModel):
    _inherit = 'res.config.settings'

    module_base_tier_validation_formula = fields.Boolean(string='Tier Formula')
    # module_base_tier_validation_forward = fields.Boolean('Tier Forward & Backward')
    # module_base_tier_validation_server_action = fields.Boolean('Tier Server Action')
    # module_base_tier_validation_report = fields.Boolean('Tier Reports')
