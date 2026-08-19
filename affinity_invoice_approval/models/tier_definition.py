from odoo import api, models


class TierDefinitionInherit(models.Model):
    _inherit = 'tier.definition'

    @api.model
    def _get_tier_validation_model_names(self):
        res = super()._get_tier_validation_model_names()
        res.append('account.move')
        return res
