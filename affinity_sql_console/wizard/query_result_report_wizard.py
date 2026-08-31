import json
from odoo import fields, models


class QueryResultReportWizard(models.TransientModel):
    _name = 'query.result.report.wizard'
    _description = 'SQL Query Result Export Wizard'

    query_id = fields.Many2one(comodel_name='sql.console', string='SQL Console Reference', required=True,
                               ondelete='cascade')
    pdf_orientation = fields.Selection(selection=[
        ('landscape', 'Landscape'),
        ('portrait', 'Portrait')
    ], string='Page Orientation', required=True, default='landscape',
        help='Select the page layout format for the generated PDF report.')
    is_report_mode = fields.Boolean(string='Is Report Mode', default=False)

    def _get_report_data(self):
        self.ensure_one()
        headers = []
        datas = []
        field_types = []

        if self.query_id and self.query_id.query_result_json:
            json_data = json.loads(self.query_id.query_result_json)
            if self.is_report_mode:
                headers = json_data.get('headers', [])
                datas = json_data.get('datas', [])
                field_types = json_data.get('field_types', [None] * len(headers))
            else:
                if self.query_id.query_statement:
                    try:
                        raw_headers, raw_datas, _ = self.query_id._get_result_from_query(self.query_id.query_statement)
                        headers = [self.query_id._format_column_header_raw(h) for h in raw_headers]
                        datas = raw_datas
                        field_types = self.query_id._get_field_types_map(raw_headers, self.query_id.query_statement)
                    except Exception:
                        headers = json_data.get('headers', [])
                        datas = json_data.get('datas', [])
                        field_types = json_data.get('field_types', [None] * len(headers))

        user_tz = self.env.user.tz or 'UTC'
        local_execution_date = fields.Datetime.context_timestamp(
            self.with_context(tz=user_tz),
            self.query_id.last_execution_date or fields.Datetime.now()
        ).strftime('%Y-%m-%d %H:%M:%S')

        return {
            'query_statement': self.query_id.query_statement or '',
            'execution_time': self.query_id.execution_time or '0s',
            'row_count': len(datas),
            'executed_by': self.query_id.last_executed_by.name or self.env.user.name,
            'execution_date': local_execution_date,
            'headers': headers,
            'datas': datas,
            'field_types': field_types,
        }

    def generate_excel_report(self):
        self.ensure_one()
        return self.env.ref('affinity_sql_console.action_report_query_result_xlsx').report_action(self)

    def generate_pdf_report(self):
        self.ensure_one()
        action_print_pdf = self.env.ref('affinity_sql_console.action_report_query_result_pdf')
        if self.pdf_orientation == 'landscape':
            action_print_pdf.paperformat_id.orientation = 'Landscape'
        elif self.pdf_orientation == 'portrait':
            action_print_pdf.paperformat_id.orientation = 'Portrait'

        return action_print_pdf.report_action(self)
