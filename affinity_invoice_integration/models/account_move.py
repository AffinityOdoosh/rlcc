from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_api_fetched = fields.Boolean(string='Fetched from API', default=False, copy=False, readonly=True)
    api_fetch_log_id = fields.Many2one(comodel_name='api.fetch.log', string='API Fetch Log', readonly=True,
                                       help='Link to the execution log generated during API sync.')

    def unlink(self):
        logs_to_update = {}
        user_name = self.env.user.name
        delete_time = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for move in self:
            if move.api_fetch_log_id:
                log = move.api_fetch_log_id
                card_html = f'''
                <div class="card mb-3 border-danger shadow-sm">
                    <div class="card-header bg-danger text-white fw-bold py-1 px-3">
                        JV ID: {move.id}
                    </div>
                    <div class="card-body py-2 px-3 bg-light">
                        <div class="row">
                            <div class="col-6 mb-1"><strong>Reference:</strong> {move.ref or 'N/A'}</div>
                            <div class="col-6 mb-1"><strong>Posting Date:</strong> {move.date}</div>
                            <div class="col-6 mb-1"><strong>Deleted By:</strong> {user_name}</div>
                            <div class="col-6 mb-1"><strong>Deleted At:</strong> {delete_time}</div>
                        </div>
                    </div>
                </div>
                '''
                if log.id not in logs_to_update:
                    logs_to_update[log.id] = []
                logs_to_update[log.id].append(card_html)

        for log_id, entries in logs_to_update.items():
            log = self.env['api.fetch.log'].browse(log_id)
            if log.exists():
                existing_log = log.deletion_log or ''
                new_entries_html = ''.join(entries)
                updated_log = f"{existing_log}{new_entries_html}"
                log.write({'deletion_log': updated_log})

        res = super(AccountMove, self).unlink()
        return res
