from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    has_wth_tax = fields.Boolean(string='Has WHT Tax')
    is_from_wizard = fields.Boolean(string='Is From Wizard', default=False)
    wht_line_ids = fields.One2many(comodel_name='withholding.line', inverse_name='payment_id',
                                   string='Withholding Lines')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            is_wiz = vals.get('is_from_wizard', False)
            if not is_wiz and 'wht_line_ids' in vals and 'amount' in vals:
                wht_amount = 0.0
                for cmd in vals['wht_line_ids']:
                    if cmd[0] == 0 and isinstance(cmd[2], dict):
                        wht_amount += cmd[2].get('amount', 0.0)
                    elif cmd[0] == 4:
                        wht_amount += self.env['withholding.line'].browse(cmd[1]).amount
                    elif cmd[0] == 6:
                        wht_amount += sum(self.env['withholding.line'].browse(cmd[2]).mapped('amount'))
                if wht_amount:
                    vals['amount'] -= wht_amount
        return super(AccountPayment, self).create(vals_list)

    def write(self, vals):
        if 'wht_line_ids' in vals and 'amount' not in vals and len(self) == 1:
            rec = self
            old_wht = sum(rec.wht_line_ids.mapped('amount'))
            new_wht = old_wht
            for cmd in vals['wht_line_ids']:
                if cmd[0] == 0:
                    new_wht += cmd[2].get('amount', 0.0)
                elif cmd[0] == 1 and 'amount' in cmd[2]:
                    new_wht -= self.env['withholding.line'].browse(cmd[1]).amount
                    new_wht += cmd[2]['amount']
                elif cmd[0] in (2, 3):
                    new_wht -= self.env['withholding.line'].browse(cmd[1]).amount
                elif cmd[0] == 5:
                    new_wht = 0.0
                elif cmd[0] == 6:
                    new_wht = sum(self.env['withholding.line'].browse(cmd[2]).mapped('amount'))

            diff = new_wht - old_wht
            if diff != 0:
                vals['amount'] = rec.amount - diff

        if 'wht_line_ids' in vals:
            for rec in self:
                if rec.move_id and rec.move_id.state == 'posted':
                    rec.move_id.button_draft()

                wht_accounts = rec.wht_line_ids.mapped('account_id')
                tax_accounts = rec.wht_line_ids.mapped('tax_id.invoice_repartition_line_ids.account_id')
                all_account_ids = set((wht_accounts | tax_accounts).ids)

                for cmd in vals['wht_line_ids']:
                    if cmd[0] in (0, 1) and isinstance(cmd[2], dict):
                        if 'account_id' in cmd[2] and cmd[2]['account_id']:
                            all_account_ids.add(cmd[2]['account_id'])
                        if 'tax_id' in cmd[2] and cmd[2]['tax_id']:
                            tax = self.env['account.tax'].browse(cmd[2]['tax_id'])
                            all_account_ids.update(tax.invoice_repartition_line_ids.mapped('account_id').ids)

                all_account_ids.discard(False)

                lines_to_delete = rec.move_id.line_ids.filtered(
                    lambda l: l.account_id.id in all_account_ids and l.account_id.id not in (
                        rec.destination_account_id.id,
                        rec.journal_id.default_account_id.id
                    )
                )
                if lines_to_delete:
                    lines_to_delete.with_context(check_move_validity=False).unlink()

        return super(AccountPayment, self).write(vals)

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        res = super()._get_trigger_fields_to_synchronize()
        return res + ('wht_line_ids', 'has_wth_tax')

    def _prepare_move_lines_per_type(self, write_off_line_vals=None, force_balance=None):
        write_off_line_vals = list(write_off_line_vals or [])

        for wht in self.wht_line_ids:
            account = wht.account_id
            if not account and wht.tax_id:
                account = wht.tax_id.invoice_repartition_line_ids.filtered(
                    lambda r: r.repartition_type == 'tax' and r.account_id
                ).account_id[:1]

            if not account:
                raise UserError(_('WHT account missing for: %s') % (wht.description or 'Withholding Tax'))

            sign = 1 if self.payment_type == 'inbound' else -1
            wht_balance = wht.amount * sign

            write_off_line_vals.append({
                'name': wht.description or 'Withholding Tax',
                'account_id': account.id,
                'currency_id': self.currency_id.id,
                'amount_currency': wht_balance,
                'balance': wht_balance,
                'partner_id': self.partner_id.id,
            })

        return super()._prepare_move_lines_per_type(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )
