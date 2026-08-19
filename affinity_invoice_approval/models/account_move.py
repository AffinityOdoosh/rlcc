from odoo import models


class AccountMoveInherit(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'tier.validation']
    _state_from = ['draft', 'cancel']
    _state_to = ['posted']

    _tier_validation_manual_config = False

    def _get_requested_notification_subtype(self):
        return 'affinity_invoice_approval.account_payment_tier_validation_requested'

    def _get_accepted_notification_subtype(self):
        return 'affinity_invoice_approval.account_payment_tier_validation_accepted'

    def _get_rejected_notification_subtype(self):
        return 'affinity_invoice_approval.account_payment_tier_validation_rejected'
