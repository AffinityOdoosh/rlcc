from odoo import models, fields, api


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    amount_withholding = fields.Monetary(string='Withholding Amount', compute='_compute_invoice_withholding_taxes',
                                         store=True)
    wht_executed = fields.Boolean(string='WHT Executed')

    @api.depends(
        'line_ids.withholding_tax_ids',
        'line_ids.withholding_subtotal'
    )
    def _compute_invoice_withholding_taxes(self):
        for move in self:
            move.amount_withholding = sum(
                move.invoice_line_ids.mapped('withholding_subtotal')
            ) if move.invoice_line_ids else 0.0
