from odoo import api, fields, models, _


class RecordExpenseLine(models.Model):
    _name = 'record.expense.line'
    _description = 'Expense Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    record_expense_id = fields.Many2one(comodel_name='record.expense', ondelete='cascade', index=True)
    account_id = fields.Many2one(comodel_name='account.account', required=True, tracking=True)
    description = fields.Char(tracking=True)
    partner_id = fields.Many2one(comodel_name='res.partner', tracking=True)
    analytical_field = fields.Json(string='Analytic Distribution')
    company_id = fields.Many2one(comodel_name='res.company', related='record_expense_id.company_id', store=True,
                                 readonly=True)
    currency_id = fields.Many2one(comodel_name='res.currency', related='company_id.currency_id', store=True,
                                  readonly=True)
    amount = fields.Monetary(string='Amount', required=True, tracking=True, currency_field='currency_id')
    analytic_precision = fields.Integer(string='Analytic Precision', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        parents = records.mapped('record_expense_id')
        for parent in parents:
            parent.message_post(body=_('Expense line added'))
        return records

    def write(self, vals):
        res = super().write(vals)
        parents = self.mapped('record_expense_id')
        for parent in parents:
            parent.message_post(body=_('Expense line updated'))
        return res

    def unlink(self):
        parents = self.mapped('record_expense_id')
        res = super().unlink()
        for parent in parents:
            parent.message_post(body=_('Expense line removed'))
        return res

    def get_analytic_distribution_details(self):
        self.ensure_one()  # always good to ensure single record
        result = []
        if not self.analytic_distribution:
            return result

        analytic_ids = [int(k) for k in self.analytic_distribution.keys()]
        accounts = self.env['account.analytic.account'].browse(analytic_ids)

        for account in accounts:
            result.append({
                'name': account.name,
                'percentage': self.analytic_distribution.get(str(account.id)),
            })
        return result
