from odoo import models, fields, api
from odoo.fields import Command


class AccountPaymentRegisterInherit(models.TransientModel):
    _inherit = 'account.payment.register'

    wht_tax_line_ids = fields.One2many(comodel_name='withholding.tax.line', inverse_name='payment_register_id',
                                       string='Withholding Tax Lines')
    wht_total = fields.Float(string='Withholding Total', compute='_compute_wht_total', store=True)

    @api.model
    def default_get(self, fields_list):
        res = super(AccountPaymentRegisterInherit, self).default_get(fields_list)
        active_ids = self._context.get('active_ids', [])
        active_model = self._context.get('active_model')
        moves = self.env['account.move']

        if active_model == 'account.move' and active_ids:
            moves = self.env['account.move'].browse(active_ids)
        elif active_model == 'account.move.line' and active_ids:
            move_lines = self.env['account.move.line'].browse(active_ids)
            moves = move_lines.move_id

        if moves:
            lines = []
            tax_amounts = {}

            wizard_currency_id = res.get('currency_id')
            if wizard_currency_id:
                wizard_currency = self.env['res.currency'].browse(wizard_currency_id)
            else:
                wizard_currency = self.env.company.currency_id

            unique_currencies = moves.mapped('currency_id')
            has_multiple_currencies = len(unique_currencies) > 1

            executed_moves = moves.filtered(lambda m: getattr(m, 'wht_executed', False))
            non_executed_moves = moves.filtered(lambda m: not getattr(m, 'wht_executed', False))

            if non_executed_moves:
                for move in non_executed_moves:
                    processed_taxes_per_move = set()
                    invoice_currency = move.currency_id

                    for line in move.invoice_line_ids:
                        for tax in getattr(line, 'withholding_tax_ids', []):
                            if tax.id in processed_taxes_per_move:
                                continue
                            processed_taxes_per_move.add(tax.id)
                            amount = 0.0

                            for ml in move.invoice_line_ids:
                                if tax not in getattr(ml, 'withholding_tax_ids', []):
                                    continue
                                tax_type = getattr(tax, 'tax_type', '')
                                if tax_type == 'standard':
                                    amount += (tax.amount / 100) * ml.price_subtotal
                                elif tax_type == 'with_sales':
                                    tax_amount = sum(ml.tax_ids.mapped('amount'))
                                    base = ml.price_subtotal + ((tax_amount / 100) * ml.price_subtotal)
                                    amount += (tax.amount / 100) * base
                                elif tax_type == 'on_sales':
                                    tax_amount = sum(ml.tax_ids.mapped('amount'))
                                    amount += (tax.amount / 100) * ((tax_amount / 100) * ml.price_subtotal)

                            if amount:
                                if has_multiple_currencies and invoice_currency != wizard_currency:
                                    amount = invoice_currency._convert(
                                        amount,
                                        wizard_currency,
                                        move.company_id,
                                        move.date or fields.Date.today()
                                    )
                                tax_amounts[tax] = tax_amounts.get(tax, 0.0) + amount

            if executed_moves:
                move_names = executed_moves.mapped('name')
                jv = self.env['account.move'].search([('ref', 'in', move_names)])
                for move in executed_moves:
                    processed_taxes_per_move = set()
                    invoice_currency = move.currency_id

                    for line in move.invoice_line_ids:
                        for tax in getattr(line, 'withholding_tax_ids', []):
                            if tax.id in processed_taxes_per_move:
                                continue
                            processed_taxes_per_move.add(tax.id)
                            amount = 0.0

                            for ml in move.invoice_line_ids:
                                if tax not in getattr(ml, 'withholding_tax_ids', []):
                                    continue
                                tax_type = getattr(tax, 'tax_type', '')
                                if tax_type == 'standard':
                                    amount += (tax.amount / 100) * ml.price_subtotal
                                elif tax_type == 'with_sales':
                                    tax_amount = sum(ml.tax_ids.mapped('amount'))
                                    base = ml.price_subtotal + ((tax_amount / 100) * ml.price_subtotal)
                                    amount += (tax.amount / 100) * base
                                elif tax_type == 'on_sales':
                                    tax_amount = sum(ml.tax_ids.mapped('amount'))
                                    amount += (tax.amount / 100) * ((tax_amount / 100) * ml.price_subtotal)

                            if amount and has_multiple_currencies and invoice_currency != wizard_currency:
                                amount = invoice_currency._convert(
                                    amount,
                                    wizard_currency,
                                    move.company_id,
                                    move.date or fields.Date.today()
                                )

                            if jv:
                                for journal in jv:
                                    for jl in journal.line_ids:
                                        if jl.name == tax.name:
                                            jv_amount = jl.credit
                                            if has_multiple_currencies and wizard_currency != self.env.company.currency_id:
                                                jv_amount = self.env.company.currency_id._convert(
                                                    jv_amount,
                                                    wizard_currency,
                                                    move.company_id,
                                                    move.date or fields.Date.today()
                                                )
                                            amount -= jv_amount

                            if amount > 0.01:
                                tax_amounts[tax] = tax_amounts.get(tax, 0.0) + amount

            for tax, total_amount in tax_amounts.items():
                account = tax.invoice_repartition_line_ids.mapped('account_id')[:1]
                lines.append(Command.create({
                    'tax_id': tax.id,
                    'account_id': account.id if account else False,
                    'description': tax.name,
                    'withholding_amount': total_amount,
                    'manually_added': False,
                }))

            if lines:
                res.update({
                    'wht_tax_line_ids': lines
                })

        return res

    @api.depends('wht_tax_line_ids.withholding_amount')
    def _compute_wht_total(self):
        for rec in self:
            rec.wht_total = sum(rec.wht_tax_line_ids.mapped('withholding_amount'))

    @api.depends('wht_total')
    def _compute_amount(self):
        for wizard in self:
            total_amounts = wizard._get_total_amounts_to_pay(wizard.batches)
            base_amount = total_amounts.get('amount_for_difference', 0.0)
            if wizard.wht_total:
                wizard.amount = base_amount - wizard.wht_total
            else:
                wizard.amount = base_amount

    @api.depends('can_edit_wizard', 'amount', 'installments_mode', 'wht_total')
    def _compute_payment_difference(self):
        for wizard in self:
            if wizard.payment_date:
                total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
                adjusted_amount = wizard.amount + wizard.wht_total
                if wizard.installments_mode in ('overdue', 'next', 'before_date'):
                    wizard.payment_difference = total_amount_values['amount_for_difference'] - adjusted_amount
                elif wizard.installments_mode == 'full':
                    wizard.payment_difference = total_amount_values['full_amount_for_difference'] - adjusted_amount
                else:
                    wizard.payment_difference = total_amount_values['amount_for_difference'] - adjusted_amount
            else:
                wizard.payment_difference = 0.0

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals['is_from_wizard'] = True
        wht_lines = []
        if self.wht_tax_line_ids:
            for rec in self.wht_tax_line_ids:
                if rec.account_id:
                    wht_lines.append(Command.create({
                        'account_id': rec.account_id.id,
                        'tax_id': rec.tax_id.id if rec.tax_id else False,
                        'description': rec.description,
                        'amount': rec.withholding_amount,
                    }))
        payment_vals.update({
            'has_wth_tax': True,
            'wht_line_ids': wht_lines if wht_lines else False
        })
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        payment_vals['is_from_wizard'] = True
        move_lines = self.env['account.move.line'].browse([line.id for line in batch_result['lines']])
        moves = move_lines.move_id

        if not moves:
            return payment_vals

        wizard_currency = self.currency_id or self.env.company.currency_id
        batch_currency = moves[:1].currency_id or wizard_currency

        wht_lines = []
        batch_wht_total_batch_currency = 0.0

        manual_no_tax_lines = self.wht_tax_line_ids.filtered(lambda l: l.manually_added and not l.tax_id)
        tax_based_lines = self.wht_tax_line_ids.filtered(lambda l: l.tax_id)

        context_active_ids = self._context.get('active_ids', [])
        context_active_model = self._context.get('active_model')
        all_wizard_moves = self.env['account.move']
        if context_active_model == 'account.move' and context_active_ids:
            all_wizard_moves = self.env['account.move'].browse(context_active_ids)
        elif context_active_model == 'account.move.line' and context_active_ids:
            all_wizard_moves = self.env['account.move.line'].browse(context_active_ids).move_id

        for rec in manual_no_tax_lines:
            if not rec.account_id:
                continue

            allocated_amount_batch = rec.withholding_amount

            batch_wht_total_batch_currency += allocated_amount_batch
            wht_lines.append(Command.create({
                'account_id': rec.account_id.id,
                'tax_id': False,
                'description': rec.description,
                'amount': allocated_amount_batch,
            }))

        for rec in tax_based_lines:
            if not rec.account_id:
                continue

            allocated_amount_batch = 0.0

            if rec.manually_added:
                tax_type = getattr(rec.tax_id, 'tax_type', '')
                invoice_total_base = 0.0
                batch_total_base = 0.0

                for m in all_wizard_moves:
                    m_base = sum(m.invoice_line_ids.filtered(
                        lambda l: rec.tax_id in getattr(l, 'withholding_tax_ids', [])).mapped('price_subtotal'))
                    if not m_base:
                        m_base = sum(m.invoice_line_ids.mapped('price_subtotal'))

                    if tax_type == 'with_sales':
                        sales_tax_amount = sum(sum(line.tax_ids.mapped('amount')) for line in m.invoice_line_ids)
                        if sales_tax_amount:
                            m_base = m_base + ((sales_tax_amount / 100) * m_base)
                    elif tax_type == 'on_sales':
                        sales_tax_amount = sum(sum(line.tax_ids.mapped('amount')) for line in m.invoice_line_ids)
                        if sales_tax_amount:
                            m_base = (sales_tax_amount / 100) * m_base
                        else:
                            m_base = 0.0

                    if m_base > 0.0:
                        if m.currency_id != wizard_currency:
                            m_base = m.currency_id._convert(
                                m_base, wizard_currency, m.company_id, m.date or fields.Date.today()
                            )
                        invoice_total_base += m_base

                        if m in moves:
                            batch_total_base += m_base

                if invoice_total_base > 0.0:
                    ratio = batch_total_base / invoice_total_base
                    allocated_amount_wizard = rec.withholding_amount * ratio
                else:
                    allocated_amount_wizard = 0.0

                if allocated_amount_wizard > 0.0:
                    allocated_amount_batch = allocated_amount_wizard
                    if wizard_currency != batch_currency:
                        allocated_amount_batch = wizard_currency._convert(
                            allocated_amount_wizard,
                            batch_currency,
                            self.company_id or self.env.company,
                            self.payment_date or fields.Date.today()
                        )
            else:
                for move in moves:
                    processed_taxes_per_move = set()
                    for line in move.invoice_line_ids:
                        for tax in getattr(line, 'withholding_tax_ids', []):
                            if tax.id != rec.tax_id.id or tax.id in processed_taxes_per_move:
                                continue
                            processed_taxes_per_move.add(tax.id)
                            amount = 0.0
                            for ml in move.invoice_line_ids:
                                if tax not in getattr(ml, 'withholding_tax_ids', []):
                                    continue
                                tax_type = getattr(tax, 'tax_type', '')
                                if tax_type == 'standard':
                                    amount += (tax.amount / 100) * ml.price_subtotal
                                elif tax_type == 'with_sales':
                                    tax_amount = sum(ml.tax_ids.mapped('amount'))
                                    base = ml.price_subtotal + ((tax_amount / 100) * ml.price_subtotal)
                                    amount += (tax.amount / 100) * base
                                elif tax_type == 'on_sales':
                                    tax_amount = sum(ml.tax_ids.mapped('amount'))
                                    amount += (tax.amount / 100) * ((tax_amount / 100) * ml.price_subtotal)

                            if amount > 0.0:
                                if move.currency_id != batch_currency:
                                    amount = move.currency_id._convert(
                                        amount, batch_currency, move.company_id, move.date or fields.Date.today()
                                    )
                                allocated_amount_batch += amount

            if allocated_amount_batch:
                batch_wht_total_batch_currency += allocated_amount_batch
                wht_lines.append(Command.create({
                    'account_id': rec.account_id.id,
                    'tax_id': rec.tax_id.id,
                    'description': rec.description,
                    'amount': allocated_amount_batch,
                }))

        if batch_wht_total_batch_currency:
            payment_vals['amount'] = payment_vals.get('amount', 0.0) - batch_wht_total_batch_currency
            payment_vals.update({
                'has_wth_tax': True,
                'wht_line_ids': wht_lines if wht_lines else False
            })

        return payment_vals
