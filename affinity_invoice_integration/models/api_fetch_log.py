from odoo import models, fields, _


class ApiFetchLog(models.Model):
    _name = 'api.fetch.log'
    _description = 'API Fetch Log'
    _order = 'create_date desc'

    name = fields.Char(string='Log Reference', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('api.fetch.log.sequence') or _('New'))
    date_from = fields.Date(string='From Date', readonly=True)
    date_to = fields.Date(string='To Date', readonly=True)
    execution_time = fields.Datetime(string='Execution Time', default=fields.Datetime.now, readonly=True)
    status = fields.Selection(selection=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
    ], string='Status', required=True, default='success', readonly=True)
    total_retrieved = fields.Integer(string='Total Retrieved', default=0, readonly=True)
    total_skipped = fields.Integer(string='Total Skipped', default=0, readonly=True)
    total_created = fields.Integer(string='Total Created', default=0, readonly=True)
    error_message = fields.Html(string='Error / Status', readonly=True)
    unmapped_accounts_log = fields.Html(string='Unmapped Accounts Log', readonly=True)
    deletion_log = fields.Html(string='Deletion Log History', readonly=True,
                               help='Tracks deleted Journal Entries associated with this execution log.')
    move_ids = fields.One2many(comodel_name='account.move', inverse_name='api_fetch_log_id',
                               string='Generated Journal Entries', readonly=True)
