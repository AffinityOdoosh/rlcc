from odoo import models


class RecordExpenseInherit(models.Model):
    _name = 'record.expense'
    _inherit = ['record.expense', 'tier.validation']
    _state_from = ['draft']
    _state_to = ['posted']

    _tier_validation_manual_config = False

    def _get_requested_notification_subtype(self):
        return 'affinity_record_expense_approval.expense_module_tier_validation_requested'

    def _get_accepted_notification_subtype(self):
        return 'affinity_record_expense_approval.expense_module_tier_validation_accepted'

    def _get_rejected_notification_subtype(self):
        return 'affinity_record_expense_approval.expense_module_tier_validation_rejected'
