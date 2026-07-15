from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import _


class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    withholding_subtotal = fields.Monetary(string='Withholding Subtotal', compute='_compute_withholding_subtotal')
    withholding_tax_ids = fields.Many2many(comodel_name='account.tax', relation='account_move_line_withholding_tax_rel',
                                           string='Withholding Tax', domain=[('type_tax_use', '=', 'withholding')])

    @api.onchange('withholding_tax_ids')
    def onchange_withholding_tax_ids(self):
        for rec in self:
            if rec.withholding_tax_ids:
                for tax in rec.withholding_tax_ids:
                    if not tax.invoice_repartition_line_ids:
                        raise ValidationError(_(
                            'Warning, please set account in Tax/Withholding Tax (%s, %s)'
                        ) % (tax.id, tax.name or ''))

                    for line in tax.invoice_repartition_line_ids:
                        if not line.account_id and line.repartition_type == 'tax':
                            raise ValidationError(_(
                                'Warning, please set account in Tax/Withholding Tax (%s, %s)'
                            ) % (tax.id, tax.name or ''))

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            taxes = rec.product_id.withholding_tax_ids
            if taxes:
                for tax in taxes:
                    if not tax.invoice_repartition_line_ids:
                        raise ValidationError(
                            _('Warning, please set account in Tax/Withholding Tax (%s, %s)') % (tax.id, tax.name or ''))

                    for line in tax.invoice_repartition_line_ids:
                        if not line.account_id and line.repartition_type == 'tax':
                            raise ValidationError(
                                _('Warning, please set account in Tax/Withholding Tax (%s, %s)') % (tax.id,
                                                                                                    tax.name or ''))

                rec.withholding_tax_ids = [(6, 0, taxes.ids)]
            else:
                rec.withholding_tax_ids = [(5, 0, 0)]

    @api.depends(
        'quantity',
        'price_unit',
        'tax_ids',
        'withholding_tax_ids'
    )
    def _compute_withholding_subtotal(self):
        for rec in self:
            if not rec.withholding_tax_ids:
                rec.withholding_subtotal = 0.0
                continue

            untaxed = rec.quantity * rec.price_unit
            tax_amount = sum(rec.tax_ids.mapped('amount'))

            total = 0.0

            for tax in rec.withholding_tax_ids:
                if getattr(tax, 'tax_type', '') == 'standard':
                    total += (tax.amount / 100) * untaxed
                elif getattr(tax, 'tax_type', '') == 'with_sales':
                    base = untaxed + ((tax_amount / 100) * untaxed)
                    total += (tax.amount / 100) * base
                elif getattr(tax, 'tax_type', '') == 'on_sales':
                    total += (tax.amount / 100) * ((tax_amount / 100) * untaxed)

            rec.withholding_subtotal = total
