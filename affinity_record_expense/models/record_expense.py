from num2words import num2words

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RecordExpense(models.Model):
    _name = 'record.expense'
    _description = 'Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', default=lambda self: _('New'), required=True, copy=False, readonly=True,
                       index=True, tracking=True)
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], default='draft', tracking=True)
    company_id = fields.Many2one(comodel_name='res.company', default=lambda self: self.env.company, required=True)
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True, tracking=True,
                                 domain="[('company_id', '=', company_id)]")
    account_id = fields.Many2one(comodel_name='account.account', string='Credit Account', required=True, tracking=True)
    currency_id = fields.Many2one(comodel_name='res.currency', related='company_id.currency_id', store=True,
                                  readonly=True)
    paid_to = fields.Char(tracking=True)
    memo = fields.Text(tracking=True)
    date = fields.Date(string='Accounting Date', default=fields.Date.context_today, tracking=True, required=True)
    posting_date = fields.Date(default=fields.Date.context_today, readonly=True)
    payment_date = fields.Date(string='Payment Date', required=True, tracking=True)
    cheque_number = fields.Char(tracking=True)
    record_expense_line_ids = fields.One2many(comodel_name='record.expense.line', inverse_name='record_expense_id',
                                              string='Expense Lines', copy=True)
    move_id = fields.Many2one(comodel_name='account.move', string='Journal Entry', copy=False, readonly=True)
    cancelled_move_ids = fields.One2many(comodel_name='account.move', inverse_name='cancelled_expense_id',
                                         string='Cancelled Journal Entries', readonly=True)
    total_expense = fields.Monetary(compute='_compute_total_expense', store=True, tracking=True)
    amount_in_words = fields.Char(compute='_compute_amount_in_words')
    payment_method = fields.Selection(selection=[
        ('cheque', 'Cheque'),
        ('online', 'Online'),
        ('cash', 'Cash'),
    ], string='Payment Method', default='cash', tracking=True, required=True)
    approved_by = fields.Many2one(comodel_name='res.users', string='Approved By', readonly=True, copy=False)
    cancelled_move_count = fields.Integer(compute='_compute_cancelled_move_count', string='Cancelled Move Count')

    @api.depends('cancelled_move_ids')
    def _compute_cancelled_move_count(self):
        for rec in self:
            rec.cancelled_move_count = len(rec.cancelled_move_ids)

    @api.depends('record_expense_line_ids.amount')
    def _compute_total_expense(self):
        for rec in self:
            rec.total_expense = sum(rec.record_expense_line_ids.mapped('amount'))

    @api.depends('total_expense')
    def _compute_amount_in_words(self):
        for rec in self:
            rec.amount_in_words = f"{num2words(rec.total_expense, lang='en').title()} Only" if rec.total_expense else False

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id and self.journal_id.default_account_id:
            self.account_id = self.journal_id.default_account_id

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('Exp_Seq') or _('New')
        return super(RecordExpense, self).create(vals)

    def write(self, vals):
        res = super(RecordExpense, self).write(vals)
        if self.env.context.get('skip_expense_sync'):
            return res

        for rec in self:
            if rec.state == 'draft' and rec.move_id and rec.move_id.state == 'draft':
                fields_to_check = ['record_expense_line_ids', 'journal_id', 'account_id', 'date', 'cheque_number',
                                   'memo']
                if any(f in vals for f in fields_to_check):
                    move_lines = []
                    total = 0.0
                    partner_id = False

                    for line in rec.record_expense_line_ids:
                        total += line.amount
                        move_lines.append((0, 0, {
                            'name': line.description or False,
                            'account_id': line.account_id.id,
                            'debit': line.amount,
                            'partner_id': line.partner_id.id or False,
                        }))
                        partner_id = partner_id or line.partner_id.id

                    credit_account = rec.account_id

                    move_vals = {
                        'journal_id': rec.journal_id.id,
                        'date': rec.date,
                        'ref': rec.name,
                        'cheque_number': rec.cheque_number,
                        'line_ids': [(5, 0, 0)] + move_lines + [(0, 0, {
                            'name': rec.memo or False,
                            'account_id': credit_account.id,
                            'credit': total,
                            'partner_id': partner_id,
                        })],
                    }
                    rec.move_id.with_context(skip_expense_sync=True).write(move_vals)
        return res

    def action_post(self):
        for rec in self:
            if rec.state == 'posted':
                raise UserError(_('This record has already been posted and cannot be posted again.'))
            if not rec.record_expense_line_ids:
                raise UserError(_('At least one expense line must be defined before posting this record.'))
            if not rec.account_id:
                raise UserError(
                    _('Credit account is not configured on this record. Please select a Credit Account first.'))

            move_lines = []
            total = 0.0
            partner_id = False
            for line in rec.record_expense_line_ids:
                total += line.amount
                move_lines.append((0, 0, {
                    'name': line.description or False,
                    'account_id': line.account_id.id,
                    'debit': line.amount,
                    'partner_id': line.partner_id.id or False,
                }))
                partner_id = partner_id or line.partner_id.id
            credit_account = rec.account_id

            move_vals = {
                'journal_id': rec.journal_id.id,
                'date': rec.date,
                'ref': rec.name,
                'cheque_number': rec.cheque_number,
                'line_ids': move_lines + [(0, 0, {
                    'name': rec.memo or False,
                    'account_id': credit_account.id,
                    'credit': total,
                    'partner_id': partner_id,
                })],
                'expense_id': rec.id,
            }

            if rec.move_id:
                move = rec.move_id
                move_vals['line_ids'] = [(5, 0, 0)] + move_vals['line_ids']
                move.with_context(skip_expense_sync=True).write(move_vals)
            else:
                move = self.env['account.move'].with_context(skip_expense_sync=True).create(move_vals)

            move.with_context(skip_expense_sync=True).action_post()

            rec.write({
                'state': 'posted',
                'move_id': move.id,
                'approved_by': self.env.user.id,
            })

    def action_draft(self):
        for rec in self:
            if rec.state not in ['posted', 'cancel']:
                raise UserError(_("Only posted or cancelled expenses can be reset to draft."))

            if rec.state == 'posted' and rec.move_id:
                rec.move_id.with_context(skip_expense_sync=True).button_draft()

            rec.write({
                'state': 'draft',
                'approved_by': False,
            })

    def action_open_cancelled_journal_entries(self):
        self.ensure_one()
        if self.cancelled_move_count == 1:
            return {
                'name': _('Cancelled Journal Entry'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.cancelled_move_ids[0].id,
                'target': 'current',
            }
        elif self.cancelled_move_count > 1:
            return {
                'name': _('Cancelled Journal Entries'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.cancelled_move_ids.ids)],
                'target': 'current',
            }

    def action_open_journal_entry(self):
        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }
