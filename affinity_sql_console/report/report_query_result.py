from odoo import models


class ReportQueryResultXLSX(models.AbstractModel):
    _name = 'report.report_query_result'
    _description = 'Query Result Report XLSX'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, records):
        for wizard in records:
            report_data = wizard._get_report_data()

            headers = report_data.get('headers', [])
            datas = report_data.get('datas', [])
            field_types = report_data.get('field_types', [None] * len(headers))
            is_report_mode = wizard.is_report_mode

            query_name = (
                (wizard.query_id.report_title or wizard.query_id.name)
                if is_report_mode else 'SQL QUERY RESULT'
            )

            sheet_name = 'SQL Query Result'
            worksheet = workbook.add_worksheet(sheet_name)

            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#714B67',
                'font_color': '#FFFFFF',
                'font_name': 'Segoe UI',
            })

            meta_label_format = workbook.add_format({
                'bold': True,
                'font_size': 9,
                'font_color': '#64748B',
                'bg_color': '#F8FAFC',
                'align': 'left',
                'valign': 'vcenter',
                'font_name': 'Segoe UI',
                'border': 1,
                'border_color': '#E2E8F0',
            })

            meta_val_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'font_color': '#1E293B',
                'bg_color': '#F8FAFC',
                'align': 'left',
                'valign': 'vcenter',
                'font_name': 'Segoe UI',
                'border': 1,
                'border_color': '#E2E8F0',
            })

            meta_empty_format = workbook.add_format({
                'bg_color': '#F8FAFC',
                'border': 1,
                'border_color': '#E2E8F0',
            })

            header_format_center = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#714B67',
                'font_color': '#FFFFFF',
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
            })

            header_index_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#714B67',
                'font_color': '#FFFFFF',
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
            })

            cell_odd_format = workbook.add_format({
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
                'font_color': '#212529',
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
            })

            cell_even_format = workbook.add_format({
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
                'font_color': '#212529',
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
            })

            currency_symbol = self.env.company.currency_id.symbol or '$'
            num_format_str = f'"{currency_symbol}"#,##0.00'

            monetary_odd_format = workbook.add_format({
                'font_size': 10,
                'align': 'right',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
                'font_color': '#212529',
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
                'num_format': num_format_str,
            })

            monetary_even_format = workbook.add_format({
                'font_size': 10,
                'align': 'right',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
                'font_color': '#212529',
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
                'num_format': num_format_str,
            })

            index_odd_format = workbook.add_format({
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#FFFFFF',
                'font_color': '#6C757D',
                'bold': True,
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
            })

            index_even_format = workbook.add_format({
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F8F9FA',
                'font_color': '#6C757D',
                'bold': True,
                'border': 1,
                'border_color': '#DEE2E6',
                'font_name': 'Segoe UI',
            })

            total_label_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#E2E8F0',
                'font_color': '#1E293B',
                'border': 1,
                'border_color': '#CBD5E1',
                'font_name': 'Segoe UI',
            })

            monetary_total_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'right',
                'valign': 'vcenter',
                'bg_color': '#E2E8F0',
                'font_color': '#1E293B',
                'border': 1,
                'border_color': '#CBD5E1',
                'font_name': 'Segoe UI',
                'num_format': num_format_str,
            })

            total_cell_format = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#E2E8F0',
                'font_color': '#64748B',
                'border': 1,
                'border_color': '#CBD5E1',
                'font_name': 'Segoe UI',
            })

            total_cols = max(len(headers), 1)

            worksheet.set_row(0, 15)
            worksheet.set_column(0, 0, 3)

            worksheet.set_row(1, 32)
            worksheet.merge_range(1, 1, 1, total_cols + 1, query_name.upper(), title_format)

            if not is_report_mode:
                worksheet.set_row(2, 10)
                worksheet.set_row(3, 18)
                worksheet.set_row(4, 18)

                for col_idx in range(1, total_cols + 2):
                    worksheet.write(3, col_idx, '', meta_empty_format)
                    worksheet.write(4, col_idx, '', meta_empty_format)

                worksheet.write(3, 1, "EXECUTED BY:", meta_label_format)
                worksheet.write(3, 2, report_data.get('executed_by', ''), meta_val_format)

                if total_cols >= 4:
                    worksheet.write(3, 4, "EXECUTION DATE:", meta_label_format)
                    execution_date = report_data.get('execution_date')
                    worksheet.write(3, 5, str(execution_date) if execution_date else '', meta_val_format)

                worksheet.write(4, 1, "EXECUTION TIME:", meta_label_format)
                worksheet.write(4, 2, report_data.get('execution_time', ''), meta_val_format)

                if total_cols >= 4:
                    worksheet.write(4, 4, "ROWS PROCESSED:", meta_label_format)
                    worksheet.write(4, 5, report_data.get('row_count', 0), meta_val_format)

                worksheet.set_row(5, 12)
                start_row = 6
            else:
                worksheet.set_row(2, 12)
                start_row = 3

            worksheet.set_row(start_row, 24)
            worksheet.write(start_row, 1, "#", header_index_format)

            for col_idx, header in enumerate(headers, start=2):
                worksheet.write(start_row, col_idx, str(header), header_format_center)

            column_totals = [0.0] * len(headers)

            current_row = start_row + 1
            for row_idx, row_data in enumerate(datas, start=1):
                is_even = row_idx % 2 == 0
                idx_style = index_even_format if is_even else index_odd_format

                worksheet.set_row(current_row, 20)
                worksheet.write(current_row, 1, row_idx, idx_style)

                for col_idx, val in enumerate(row_data, start=2):
                    data_col_idx = col_idx - 2
                    is_monetary = is_report_mode and (data_col_idx < len(field_types)) and (
                            field_types[data_col_idx] == 'monetary')

                    if is_monetary:
                        row_style = monetary_even_format if is_even else monetary_odd_format
                        if val is not None and isinstance(val, (int, float)):
                            float_val = float(val)
                            worksheet.write_number(current_row, col_idx, float_val, row_style)
                            column_totals[data_col_idx] += float_val
                        else:
                            worksheet.write(current_row, col_idx, '', row_style)
                    else:
                        row_style = cell_even_format if is_even else cell_odd_format
                        val_to_write = '' if val is None else str(val)
                        worksheet.write(current_row, col_idx, val_to_write, row_style)

                current_row += 1

            if is_report_mode and datas:
                worksheet.set_row(current_row, 22)
                worksheet.write(current_row, 1, "Total", total_label_format)

                for data_col_idx, f_type in enumerate(field_types[:len(headers)]):
                    target_col = data_col_idx + 2
                    if f_type == 'monetary':
                        worksheet.write_number(
                            current_row,
                            target_col,
                            column_totals[data_col_idx],
                            monetary_total_format
                        )
                    else:
                        worksheet.write(current_row, target_col, "-", total_cell_format)

            worksheet.set_column(1, 1, 6)
            for col_idx, header in enumerate(headers, start=2):
                max_len = len(str(header))
                for row_data in datas:
                    val = row_data[col_idx - 2]
                    if val is not None:
                        max_len = max(max_len, len(str(val)))
                worksheet.set_column(col_idx, col_idx, min(max_len + 4, 50))
