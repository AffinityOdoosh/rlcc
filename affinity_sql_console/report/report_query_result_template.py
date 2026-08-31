from odoo import models


class ReportQueryResultTemplate(models.AbstractModel):
    _name = 'report.affinity_sql_console.report_query_result_template'
    _description = 'Query Result Report Template'

    def _get_report_values(self, docids, data=None):
        wizards = self.env['query.result.report.wizard'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'query.result.report.wizard',
            'docs': wizards,
            'company': self.env.company,
            'res_company': self.env.company,
        }
