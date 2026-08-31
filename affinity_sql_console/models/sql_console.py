import html
import json
import re
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_amount


class SqlConsole(models.Model):
    _name = 'sql.console'
    _description = 'SQL Console for PostgreSQL Queries'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    active = fields.Boolean(string='Active', default=True)
    name = fields.Char(string='Description / Purpose', required=True, translate=True,
                       help='Provide a short summary or purpose regarding this query.')
    report_title = fields.Char(string='Report Title', translate=True, copy=False,
                               help='Custom title to display on the report form for end users.')
    query_statement = fields.Text(string='SQL Query Statement', required=True, tracking=True,
                                  help='Enter the SQL query you want to execute against the database.')
    query_result = fields.Html(string='Execution Results', copy=False)
    query_result_report = fields.Html(string='Report Execution Results', copy=False)
    query_result_json = fields.Text(string='Result Data JSON', readonly=True, copy=False)
    row_count = fields.Text(string='Rows Processed', copy=False)
    raw_row_count = fields.Integer(string='Raw Row Count', default=0, copy=False)
    execution_time = fields.Char(string='Execution Time', readonly=True, copy=False,
                                 help='Time taken to execute the query in seconds and milliseconds.')
    last_executed_by = fields.Many2one(comodel_name='res.users', string='Executed By', readonly=True, copy=False,
                                       tracking=True)
    last_execution_date = fields.Datetime(string='Last Execution Date', readonly=True, copy=False, tracking=True)
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('success', 'Executed'),
        ('error', 'Failed')
    ], string='Status', default='draft', copy=False, readonly=True, tracking=True)
    is_report = fields.Boolean(string='Is Saved Report?', copy=False,
                               help='Check this to publish this query as a report in the User Reports menu.')
    has_valid_select_result = fields.Boolean(string='Has Valid Select Result', readonly=True, copy=False)
    allowed_user_ids = fields.Many2many(comodel_name='res.users', relation='sql_console_res_users_rel',
                                        column1='console_id', column2='user_id', string='Allowed Users',
                                        help='If set, only selected users can view and run this report.', copy=False)
    allowed_group_ids = fields.Many2many(comodel_name='res.groups', relation='sql_console_res_groups_rel',
                                         column1='console_id', column2='group_id', string='Allowed Groups', copy=False,
                                         help='If set, users belonging to any of these groups can view and run this report.')

    @api.constrains('allowed_user_ids', 'allowed_group_ids', 'is_report')
    def _check_and_sync_user_groups(self):
        user_group = self.env.ref('affinity_sql_console.group_sql_console_user', raise_if_not_found=False)
        if not user_group:
            return

        all_reports = self.search([('is_report', '=', True)])
        assigned_users = all_reports.mapped('allowed_user_ids')

        assigned_groups = all_reports.mapped('allowed_group_ids')
        if assigned_groups:
            group_users = self.env['res.users'].search([('groups_id', 'in', assigned_groups.ids)])
            assigned_users |= group_users

        target_users = assigned_users.sudo()
        users_to_add = target_users - user_group.users
        if users_to_add:
            user_group.sudo().write({'users': [(4, u.id) for u in users_to_add]})

        all_assigned_user_ids = set(self.search([('is_report', '=', True)]).mapped('allowed_user_ids').ids)
        all_assigned_group_ids = self.search([('is_report', '=', True)]).mapped('allowed_group_ids').ids
        if all_assigned_group_ids:
            all_assigned_user_ids.update(
                self.env['res.users'].search([('groups_id', 'in', all_assigned_group_ids)]).ids
            )

        users_to_remove = user_group.users.filtered(
            lambda u: u.id not in all_assigned_user_ids
                      and not u.has_group('affinity_sql_console.group_sql_console_manager')
        )
        if users_to_remove:
            user_group.sudo().write({'users': [(3, u.id) for u in users_to_remove]})

    def action_open_export_wizard(self):
        self.ensure_one()
        return {
            'name': _('Export Query Results'),
            'type': 'ir.actions.act_window',
            'res_model': 'query.result.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_query_id': self.id,
                'default_query_name': self.report_title or self.name,
                'default_is_report_mode': self.env.context.get('is_report_mode', False),
            },
        }

    def _get_result_from_query(self, query):
        self = self.sudo()
        headers = []
        datas = []
        affected_rows = 0

        is_admin = self.env.user.has_group('affinity_sql_console.group_sql_console')
        is_manager = self.env.user.has_group('affinity_sql_console.group_sql_console_manager')
        is_user = self.env.user.has_group('affinity_sql_console.group_sql_console_user')

        clean_query = query.strip().rstrip(';').strip()
        if not is_admin and (is_manager or is_user):
            if not clean_query.lower().startswith(('select', 'with')):
                raise UserError(_("Non-administrative users are restricted to execution of SELECT queries only."))

        with self.env.cr.savepoint():
            if not is_admin:
                self.env.cr.execute("SET TRANSACTION READ ONLY;")

            self.env.cr.execute(query)
            affected_rows = self.env.cr.rowcount

            if self.env.cr.description:
                headers = [d[0] for d in self.env.cr.description]
                datas = self.env.cr.fetchall()

        return headers, datas, affected_rows

    def _format_execution_time(self, duration_seconds):
        ms = duration_seconds * 1000
        if duration_seconds < 60:
            return f'{duration_seconds:.3f}s ({ms:.2f} ms)'

        minutes = int(duration_seconds // 60)
        rem_seconds = duration_seconds % 60
        return f'{minutes}m {rem_seconds:.3f}s ({ms:.2f} ms)'

    def _format_column_header_raw(self, raw_header):
        return raw_header

    def _format_column_header_report(self, raw_header, query_statement):
        header = raw_header
        if header.endswith('_id'):
            header = header[:-3]
        elif header.endswith('_ids'):
            header = header[:-4]

        model_name = self._detect_primary_model(query_statement)
        if model_name and model_name in self.env:
            model = self.env[model_name]
            field = model._fields.get(raw_header) or model._fields.get(header)
            if field and field.string:
                return field.string

        return header.replace('_', ' ').title()

    def _detect_primary_model(self, query):
        match = re.search(r'\bfrom\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
        if match:
            table_name = match.group(1).lower()
            for model_name, model_obj in self.env.items():
                if getattr(model_obj, '_table', None) == table_name:
                    return model_name
        return None

    def _get_field_types_map(self, headers, query_statement):
        model_name = self._detect_primary_model(query_statement)
        field_types = [None] * len(headers)
        if not model_name or model_name not in self.env:
            return field_types

        model = self.env[model_name]
        for col_idx, col_name in enumerate(headers):
            field = model._fields.get(col_name)
            if field:
                field_types[col_idx] = field.type
        return field_types

    def _resolve_report_display_values(self, headers, datas, query_statement, for_json=False):
        model_name = self._detect_primary_model(query_statement)
        if not model_name or model_name not in self.env:
            return datas

        model = self.env[model_name]
        m2o_map = {}
        selection_map = {}
        monetary_indices = {}

        default_currency = self.env.company.currency_id
        currency_col_idx = headers.index('currency_id') if 'currency_id' in headers else None

        for col_idx, col_name in enumerate(headers):
            field = model._fields.get(col_name)
            if field:
                if field.type == 'many2one':
                    rel_model_name = field.comodel_name
                    if rel_model_name in self.env:
                        ids_to_fetch = set()
                        for row in datas:
                            val = row[col_idx]
                            if isinstance(val, int):
                                ids_to_fetch.add(val)
                        if ids_to_fetch:
                            records = self.env[rel_model_name].sudo().browse(list(ids_to_fetch))
                            name_mapping = dict(records.name_get()) if hasattr(records, 'name_get') else {
                                r.id: r.display_name for r in records
                            }
                            m2o_map[col_idx] = name_mapping

                elif field.type == 'selection':
                    selection_options = field._description_selection(self.env)
                    if selection_options:
                        selection_map[col_idx] = dict(selection_options)

                elif field.type == 'monetary':
                    monetary_indices[col_idx] = getattr(field, 'currency_field', 'currency_id')

        if not m2o_map and not selection_map and not monetary_indices:
            return datas

        currency_cache = {}
        if currency_col_idx is not None:
            curr_ids = {row[currency_col_idx] for row in datas if isinstance(row[currency_col_idx], int)}
            if curr_ids:
                currencies = self.env['res.currency'].sudo().browse(list(curr_ids))
                currency_cache = {c.id: c for c in currencies}

        transformed_datas = []
        for row in datas:
            new_row = list(row)

            for col_idx, name_map in m2o_map.items():
                val = new_row[col_idx]
                if isinstance(val, int) and val in name_map:
                    new_row[col_idx] = name_map[val]

            for col_idx, sel_dict in selection_map.items():
                val = new_row[col_idx]
                if val in sel_dict:
                    new_row[col_idx] = sel_dict[val]

            for col_idx, curr_field_name in monetary_indices.items():
                val = new_row[col_idx]
                if val is not None and isinstance(val, (int, float)):
                    if not for_json:
                        row_currency = default_currency
                        if currency_col_idx is not None and isinstance(row[currency_col_idx], int):
                            row_currency = currency_cache.get(row[currency_col_idx], default_currency)
                        new_row[col_idx] = format_amount(self.env, val, row_currency)
                    else:
                        new_row[col_idx] = float(val)

            transformed_datas.append(new_row)

        return transformed_datas

    def _build_html_table(self, headers, datas, field_types=None):
        header_html = '<tr style="background-color: #714B67; color: #ffffff;">'
        header_html += '<th style="padding: 10px 14px; text-align: center; font-weight: 600; border-right: 1px solid rgba(255,255,255,0.15); width: 50px; white-space: nowrap;">#</th>'
        for idx, header in enumerate(headers):
            header_html += f'<th style="padding: 10px 14px; text-align: center; font-weight: 600; border-right: 1px solid rgba(255,255,255,0.15); white-space: nowrap;">{html.escape(str(header))}</th>'
        header_html += '</tr>'

        body_html = ''
        for i, data in enumerate(datas, start=1):
            bg_color = '#ffffff' if i % 2 != 0 else '#f8f9fa'
            body_line = f'<tr style="background-color: {bg_color}; border-bottom: 1px solid #e9ecef;">'
            body_line += f'<td style="padding: 8px 14px; font-weight: 600; color: #6c757d; border-right: 1px solid #dee2e6; text-align: center; white-space: nowrap;">{i}</td>'
            for idx, value in enumerate(data):
                display_value = ''
                if value is not None:
                    display_value = html.escape(str(value))
                align = 'right' if field_types and field_types[idx] == 'monetary' else 'center'
                body_line += f'<td style="padding: 8px 14px; color: #212529; border-right: 1px solid #e9ecef; white-space: nowrap; text-align: {align};">{display_value}</td>'
            body_line += '</tr>'
            body_html += body_line

        return f'''
        <div style="width: 100%; border: 1px solid #dee2e6; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-top: 8px; overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-family: inherit; font-size: 13px; table-layout: auto;">
                <thead>
                    {header_html}
                </thead>
                <tbody>
                    {body_html}
                </tbody>
            </table>
        </div>
        '''

    def write(self, vals):
        if 'query_statement' in vals:
            vals.update({
                'has_valid_select_result': False,
                'is_report': False,
                'query_result': False,
                'query_result_report': False,
                'query_result_json': False,
                'row_count': False,
                'raw_row_count': 0,
                'state': 'draft',
            })
        return super(SqlConsole, self).write(vals)

    def execute(self):
        for record in self:
            vals = {
                'row_count': False,
                'raw_row_count': 0,
                'query_result': False,
                'query_result_report': False,
                'query_result_json': False,
                'has_valid_select_result': False,
                'last_executed_by': self.env.user.id,
                'last_execution_date': fields.Datetime.now(),
            }

            if record.query_statement:
                start_time = time.perf_counter()
                try:
                    headers, datas, affected_rows = record._get_result_from_query(record.query_statement)
                    end_time = time.perf_counter()

                    execution_duration = end_time - start_time
                    vals['execution_time'] = record._format_execution_time(execution_duration)

                    row_count = len(datas) if headers else affected_rows
                    if row_count < 0:
                        row_count = 0

                    vals['raw_row_count'] = row_count
                    vals['row_count'] = _('{0} row{1} processed').format(row_count, 's' if row_count != 1 else '')
                    vals['state'] = 'success'

                    if headers:
                        vals['has_valid_select_result'] = True
                        field_types = record._get_field_types_map(headers, record.query_statement)

                        if datas:
                            raw_headers = [record._format_column_header_raw(h) for h in headers]
                            vals['query_result'] = record._build_html_table(raw_headers, datas, field_types)

                            report_headers = [record._format_column_header_report(h, record.query_statement) for h in
                                              headers]
                            report_datas = record._resolve_report_display_values(headers, datas, record.query_statement,
                                                                                 for_json=False)
                            vals['query_result_report'] = record._build_html_table(report_headers, report_datas,
                                                                                   field_types)

                            json_datas = record._resolve_report_display_values(headers, datas, record.query_statement,
                                                                               for_json=True)
                            vals['query_result_json'] = json.dumps({
                                'headers': report_headers,
                                'datas': json_datas,
                                'field_types': field_types,
                            }, default=str)
                        else:
                            empty_alert = '''
                            <div class="alert alert-info mt-2 mb-0" role="alert">
                                Query executed successfully, but returned 0 rows.
                            </div>
                            '''
                            vals['query_result'] = empty_alert
                            vals['query_result_report'] = empty_alert
                    else:
                        vals['is_report'] = False
                        success_alert = f'''
                        <div class="alert alert-success mt-2 mb-0" role="alert" style="border-left: 5px solid #28a745;">
                            <h5 class="alert-heading mb-1" style="font-weight: 600;">Query Executed Successfully!</h5>
                            <p class="mb-0">Statement executed without errors. <strong>{row_count}</strong> row(s) affected.</p>
                        </div>
                        '''
                        vals['query_result'] = success_alert
                        vals['query_result_report'] = success_alert

                except Exception as e:
                    end_time = time.perf_counter()
                    err_str = str(e)
                    vals['execution_time'] = record._format_execution_time(end_time - start_time)
                    vals['state'] = 'error'
                    vals['has_valid_select_result'] = False
                    vals['is_report'] = False

                    escaped_err = html.escape(err_str)
                    error_alert = f'''
                    <div class="alert alert-danger mt-2 mb-0" role="alert" style="border-left: 5px solid #dc3545; background-color: #f8d7da; border-color: #f5c6cb; color: #721c24; padding: 16px; border-radius: 6px;">
                        <h5 class="alert-heading mb-2" style="font-weight: 700; color: #721c24; font-size: 15px;">Execution Failed!</h5>
                        <p class="mb-2" style="font-size: 13px; color: #842029;">An error occurred while executing the SQL statement:</p>
                        <pre style="margin: 0; background-color: rgba(184, 40, 50, 0.08); border: 1px solid rgba(184, 40, 50, 0.2); border-radius: 4px; padding: 12px; font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 13px; color: #842029; font-weight: 600; white-space: pre-wrap; word-break: break-word; max-height: 250px; overflow-y: auto;">{escaped_err}</pre>
                    </div>
                    '''
                    vals['query_result'] = error_alert
                    vals['query_result_report'] = error_alert

            record.sudo().write(vals)
