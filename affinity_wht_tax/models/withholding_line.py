from odoo import fields, models


class WithholdingLine(models.Model):
    _name = 'withholding.line'
    _description = 'Withholding Tax Line'

    payment_id = fields.Many2one(comodel_name='account.payment', string='Payment')
    account_id = fields.Many2one(comodel_name='account.account', string='Withholding Account')
    tax_id = fields.Many2one(comodel_name='account.tax', string='Withholding Tax')
    description = fields.Char(string='Description')
    amount = fields.Float(string='Amount')
    company_id = fields.Many2one(comodel_name='res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency', related='payment_id.currency_id',
                                  store=True, readonly=True)
