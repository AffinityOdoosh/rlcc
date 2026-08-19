from odoo import models, Command


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        return super(AccountPaymentRegister, self.with_context(skip_validation=True))._create_payments()

    def _post_payments(self, to_process, edit_mode=False):
        valid_to_process = [
            vals for vals in to_process
            if not vals['payment'].need_validation
        ]
        if valid_to_process:
            super()._post_payments(valid_to_process, edit_mode=edit_mode)

        for vals in to_process:
            payment = vals['payment']
            if payment.need_validation:
                if payment.state == 'posted':
                    payment.action_draft()
                elif payment.move_id.state == 'posted':
                    payment.move_id.button_draft()
                    payment.state = 'draft'
                else:
                    payment.state = 'draft'

    def _reconcile_payments(self, to_process, edit_mode=False):
        valid_to_process = [
            vals for vals in to_process
            if not vals['payment'].need_validation
        ]
        if valid_to_process:
            super()._reconcile_payments(valid_to_process, edit_mode=edit_mode)

        for vals in to_process:
            payment = vals['payment']
            if payment.need_validation:
                lines = vals['to_reconcile']
                lines.move_id.matched_payment_ids = [Command.link(payment.id)]
