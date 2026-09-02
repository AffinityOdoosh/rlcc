import json

from odoo import api, fields, models


class QueryResultReportWizard(models.TransientModel):
    _name = 'query.result.report.wizard'
    _description = 'SQL Query Result Export Wizard'

    query_id = fields.Many2one(
        comodel_name='sql.console',
        string='SQL Console Reference',
        required=True,
        ondelete='cascade'
    )
    pdf_orientation = fields.Selection(
        selection=[
            ('landscape', 'Landscape'),
            ('portrait', 'Portrait')
        ],
        string='Page Orientation',
        required=True,
        default='landscape',
        help='Select the page layout format for the generated PDF report.'
    )
    is_report_mode = fields.Boolean(
        string='Is Report Mode',
        default=False
    )
    filter_ids = fields.One2many(
        comodel_name='query.result.report.filter',
        inverse_name='wizard_id',
        string='Filters'
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)

        query_id = self.env.context.get('default_query_id')
        if not query_id:
            return vals

        query = self.env['sql.console'].browse(query_id).exists()
        if not query:
            return vals

        vals['filter_ids'] = [
            (0, 0, {
                'field_id': field.id,
            })
            for field in query.report_filter_field_ids
        ]

        return vals

    def _get_filter_domain_values(self):
        self.ensure_one()
        filters = []

        for filter_line in self.filter_ids:
            field = filter_line.field_id
            if not field:
                continue

            field_type = field.ttype

            if field_type == 'date':
                if filter_line.date_from:
                    filters.append((field.name, '>=', filter_line.date_from))
                if filter_line.date_to:
                    filters.append((field.name, '<=', filter_line.date_to))

            elif field_type == 'datetime':
                if filter_line.datetime_from:
                    filters.append((field.name, '>=', filter_line.datetime_from))
                if filter_line.datetime_to:
                    filters.append((field.name, '<=', filter_line.datetime_to))

            elif field_type in ('integer', 'float', 'monetary'):
                if filter_line.number_from is not False:
                    filters.append((field.name, '>=', filter_line.number_from))
                if filter_line.number_to is not False:
                    filters.append((field.name, '<=', filter_line.number_to))

            elif field_type == 'boolean':
                filters.append((field.name, '=', filter_line.boolean_value))

            elif field_type in ('many2one', 'many2many', 'one2many'):
                if filter_line.value:
                    filters.append((field.name, '=', filter_line.value))

            else:
                if filter_line.value:
                    filters.append((field.name, 'ilike', filter_line.value))

        return filters

    def _apply_filters_to_data(self, headers, datas):
        self.ensure_one()

        if not datas or not self.filter_ids:
            return datas

        header_indexes = {header: index for index, header in enumerate(headers)}
        filtered_datas = []

        for row in datas:
            include_row = True

            for filter_line in self.filter_ids:
                field = filter_line.field_id
                if not field or field.name not in header_indexes:
                    continue

                value = row[header_indexes[field.name]]
                field_type = field.ttype

                if field_type == 'date':
                    if filter_line.date_from and value:
                        if value < filter_line.date_from:
                            include_row = False
                            break
                    if filter_line.date_to and value:
                        if value > filter_line.date_to:
                            include_row = False
                            break

                elif field_type == 'datetime':
                    if filter_line.datetime_from and value:
                        if value < filter_line.datetime_from:
                            include_row = False
                            break
                    if filter_line.datetime_to and value:
                        if value > filter_line.datetime_to:
                            include_row = False
                            break

                elif field_type in ('integer', 'float', 'monetary'):
                    if value is None:
                        include_row = False
                        break

                    if filter_line.number_from is not False and value < filter_line.number_from:
                        include_row = False
                        break

                    if filter_line.number_to is not False and value > filter_line.number_to:
                        include_row = False
                        break

                elif field_type == 'boolean':
                    if bool(value) != filter_line.boolean_value:
                        include_row = False
                        break

                elif field_type in ('many2one', 'many2many', 'one2many'):
                    if filter_line.value and str(value) != filter_line.value:
                        include_row = False
                        break

                else:
                    if filter_line.value and filter_line.value.lower() not in str(value or '').lower():
                        include_row = False
                        break

            if include_row:
                filtered_datas.append(row)

        return filtered_datas

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
                        raw_headers, raw_datas, _ = self.query_id._get_result_from_query(
                            self.query_id.query_statement
                        )
                        headers = [self.query_id._format_column_header_raw(h) for h in raw_headers]
                        datas = raw_datas
                        field_types = self.query_id._get_field_types_map(
                            raw_headers,
                            self.query_id.query_statement
                        )
                    except Exception:
                        headers = json_data.get('headers', [])
                        datas = json_data.get('datas', [])
                        field_types = json_data.get('field_types', [None] * len(headers))

        datas = self._apply_filters_to_data(headers, datas)

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
        return self.env.ref(
            'affinity_sql_console.action_report_query_result_xlsx'
        ).report_action(self)

    def generate_pdf_report(self):
        self.ensure_one()

        action_print_pdf = self.env.ref(
            'affinity_sql_console.action_report_query_result_pdf'
        )

        if self.pdf_orientation == 'landscape':
            action_print_pdf.paperformat_id.orientation = 'Landscape'
        elif self.pdf_orientation == 'portrait':
            action_print_pdf.paperformat_id.orientation = 'Portrait'

        return action_print_pdf.report_action(self)
