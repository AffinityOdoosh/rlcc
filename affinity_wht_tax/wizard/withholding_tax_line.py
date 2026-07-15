from odoo import models, fields, api


class WithholdingTaxLine(models.TransientModel):
    _name = 'withholding.tax.line'
    _description = 'Withholding Tax Line'

    payment_register_id = fields.Many2one(comodel_name='account.payment.register', string='Payment Register')
    tax_id = fields.Many2one(comodel_name='account.tax', string='Withholding Tax',
                             domain=[('type_tax_use', '=', 'withholding')])
    account_id = fields.Many2one(comodel_name='account.account', string='Account')
    description = fields.Char(string='Description')
    withholding_amount = fields.Float(string='Amount')
    manually_added = fields.Boolean(string='Manually Added', default=True)
    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency',
                                  related='payment_register_id.currency_id', readonly=True)

    @api.onchange('tax_id')
    def _onchange_tax_id(self):
        if not self.tax_id:
            self.description = False
            self.withholding_amount = 0.0
            self.account_id = False
            return

        self.description = self.tax_id.name

        account = self.tax_id.invoice_repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'tax' and r.account_id
        ).account_id[:1]

        if account:
            self.account_id = account.id
        else:
            self.account_id = False

        active_ids = self._context.get('active_ids', [])
        active_model = self._context.get('active_model')
        moves = self.env['account.move']

        if active_model == 'account.move' and active_ids:
            moves = self.env['account.move'].browse(active_ids)
        elif active_model == 'account.move.line' and active_ids:
            moves = self.env['account.move.line'].browse(active_ids).move_id

        if moves:
            wizard_currency = self.payment_register_id.currency_id or self.env.company.currency_id
            unique_currencies = moves.mapped('currency_id')
            has_multiple_currencies = len(unique_currencies) > 1

            total_calculated_amount = 0.0
            for move in moves:
                invoice_currency = move.currency_id
                move_amount = 0.0

                for ml in move.invoice_line_ids:
                    tax_type = getattr(self.tax_id, 'tax_type', '')

                    if tax_type == 'standard':
                        move_amount += (self.tax_id.amount / 100) * ml.price_subtotal

                    elif tax_type == 'with_sales':
                        tax_amount = sum(ml.tax_ids.mapped('amount'))
                        base = ml.price_subtotal + ((tax_amount / 100) * ml.price_subtotal)
                        move_amount += (self.tax_id.amount / 100) * base

                    elif tax_type == 'on_sales':
                        tax_amount = sum(ml.tax_ids.mapped('amount'))
                        move_amount += (self.tax_id.amount / 100) * ((tax_amount / 100) * ml.price_subtotal)

                if move_amount:
                    if has_multiple_currencies and invoice_currency != wizard_currency:
                        move_amount = invoice_currency._convert(
                            move_amount,
                            wizard_currency,
                            move.company_id,
                            move.date or fields.Date.today()
                        )
                    total_calculated_amount += move_amount

            self.withholding_amount = total_calculated_amount
