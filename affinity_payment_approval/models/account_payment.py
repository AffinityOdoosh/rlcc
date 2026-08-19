from odoo import models


class AccountPaymentInherit(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'tier.validation']
    _state_from = ['draft', 'in_process', 'canceled', 'rejected']
    _state_to = ['paid']

    _tier_validation_manual_config = False

    def _get_requested_notification_subtype(self):
        return 'affinity_payment_approval.account_payment_tier_validation_requested'

    def _get_accepted_notification_subtype(self):
        return 'affinity_payment_approval.account_payment_tier_validation_accepted'

    def _get_rejected_notification_subtype(self):
        return 'affinity_payment_approval.account_payment_tier_validation_rejected'

    def _tier_validation_check_state_on_write(self, vals):
        if self.env.context.get('skip_validation'):
            return
        return super()._tier_validation_check_state_on_write(vals)

    def _get_under_validation_exceptions(self):
        res = super()._get_under_validation_exceptions()
        return res + ['state', 'move_id']

    def _get_after_validation_exceptions(self):
        res = super()._get_after_validation_exceptions()
        return res + ['state', 'move_id']

    def action_post(self):
        res = super().action_post()
        for payment in self:
            rec_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                          and not l.reconciled
            )
            for invoice in payment.reconciled_invoice_ids:
                if invoice.state == 'posted':
                    invoice_lines = invoice.line_ids.filtered(
                        lambda l: l.account_id in rec_lines.account_id and not l.reconciled
                    )
                    if invoice_lines and rec_lines:
                        (rec_lines + invoice_lines).reconcile()
        return res
