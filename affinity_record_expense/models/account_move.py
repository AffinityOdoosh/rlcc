from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    expense_id = fields.Many2one(comodel_name='record.expense', string='Expense')
    cancelled_expense_id = fields.Many2one(comodel_name='record.expense', string='Cancelled Expense Reference')
    cheque_number = fields.Char(string='Cheque Number')

    def button_draft(self):
        for move in self:
            if move.expense_id and move in move.expense_id.cancelled_move_ids:
                raise UserError(
                    _('You cannot reset this journal entry to draft because it is a cancelled expense entry.'))
        return super().button_draft()

    def button_cancel(self):
        res = super().button_cancel()
        for move in self:
            if move.expense_id:
                expense = move.expense_id
                move.with_context(skip_expense_sync=True).write({
                    'cancelled_expense_id': expense.id,
                })
                expense.with_context(skip_expense_sync=True).write({
                    'state': 'cancel',
                    'move_id': False
                })
        return res

    def write(self, vals):
        if 'line_ids' in vals:
            for move in self:
                if move.expense_id or move.cancelled_expense_id:
                    for command in vals['line_ids']:
                        if command[0] == 1:
                            line = self.env['account.move.line'].browse(command[1])
                            if line.credit > 0 and 'account_id' in command[2]:
                                raise UserError(
                                    _('You cannot change the credit account on a journal entry linked to an expense.'))
                        elif command[0] == 2:
                            line = self.env['account.move.line'].browse(command[1])
                            if line.credit > 0:
                                raise UserError(
                                    _('You cannot delete the credit line on a journal entry linked to an expense.'))

        res = super().write(vals)
        if self.env.context.get('skip_expense_sync'):
            return res

        for move in self:
            if move.expense_id:
                expense = move.expense_id
                expense_vals = {}

                if move.state == 'posted' and expense.state != 'posted':
                    expense_vals['state'] = 'posted'
                elif move.state == 'draft' and expense.state != 'draft':
                    expense_vals['state'] = 'draft'

                if 'date' in vals:
                    expense_vals['date'] = vals['date']
                if 'journal_id' in vals:
                    expense_vals['journal_id'] = vals['journal_id']
                if 'cheque_number' in vals:
                    expense_vals['cheque_number'] = vals['cheque_number']
                if 'ref' in vals:
                    expense_vals['name'] = vals['ref']

                if expense_vals:
                    expense.with_context(skip_expense_sync=True, tracking_disable=True).write(expense_vals)

                if 'line_ids' in vals and move.state == 'draft':
                    debit_lines = move.line_ids.filtered(lambda l: l.debit > 0)
                    expense.record_expense_line_ids.with_context(tracking_disable=True).unlink()

                    new_expense_lines = []
                    for line in debit_lines:
                        new_expense_lines.append((0, 0, {
                            'account_id': line.account_id.id,
                            'description': line.name,
                            'partner_id': line.partner_id.id or False,
                            'amount': line.debit,
                        }))
                    if new_expense_lines:
                        expense.with_context(skip_expense_sync=True, tracking_disable=True).write({
                            'record_expense_line_ids': new_expense_lines
                        })
        return res

    def action_open_expense(self):
        self.ensure_one()
        return {
            'name': _('Expense'),
            'type': 'ir.actions.act_window',
            'res_model': 'record.expense',
            'view_mode': 'form',
            'res_id': self.expense_id.id,
            'target': 'current',
        }
