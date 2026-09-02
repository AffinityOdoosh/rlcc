from odoo import api, fields, models


class QueryResultReportFilter(models.TransientModel):
    _name = 'query.result.report.filter'
    _description = 'SQL Query Result Report Filter'

    wizard_id = fields.Many2one(
        comodel_name='query.result.report.wizard',
        required=True,
        ondelete='cascade'
    )
    field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade'
    )
    field_type = fields.Selection(
        related='field_id.ttype',
        string='Field Type',
        readonly=True
    )
    field_name = fields.Char(
        related='field_id.name',
        readonly=True
    )
    field_label = fields.Char(
        related='field_id.field_description',
        readonly=True
    )
    value = fields.Char(string='Value')
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    datetime_from = fields.Datetime(string='Date From')
    datetime_to = fields.Datetime(string='Date To')
    number_from = fields.Float(string='From')
    number_to = fields.Float(string='To')
    boolean_value = fields.Boolean(string='Value')

    @api.onchange('field_id')
    def _onchange_field_id(self):
        for record in self:
            record.value = False
            record.date_from = False
            record.date_to = False
            record.datetime_from = False
            record.datetime_to = False
            record.number_from = False
            record.number_to = False
            record.boolean_value = False
