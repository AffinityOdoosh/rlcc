from odoo import models, fields


class ApiFetchLog(models.Model):
    _name = 'api.fetch.log'
    _description = 'API Fetch Log'
    _order = 'create_date desc'

    execution_time = fields.Datetime(string='Execution Time', default=fields.Datetime.now, readonly=True)
    status = fields.Selection(selection=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Partial / Warning'),
    ], string='Status', required=True, default='success', readonly=True)
    date_from = fields.Date(string='From Date', readonly=True)
    date_to = fields.Date(string='To Date', readonly=True)
    total_retrieved = fields.Integer(string='Total Retrieved', readonly=True)
    total_created = fields.Integer(string='Total Created', readonly=True)
    total_skipped = fields.Integer(string='Total Skipped (Duplicates)', readonly=True)
    unmapped_accounts_log = fields.Text(string='Unmapped Accounts Detail', readonly=True)
    error_message = fields.Text(string='Error / Exception Log', readonly=True)
    move_ids = fields.Many2many(comodel_name='account.move', string='Created Journal Entries', readonly=True)
