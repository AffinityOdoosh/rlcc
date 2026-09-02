import calendar
from datetime import date, timedelta

import requests

from odoo import api, models, fields, _
from odoo.exceptions import UserError

BASE_URL = 'https://rlcc.glowsims.com/api/finance/v1'
CLIENT_ID = 'odoo_integration'
CLIENT_SECRET = 'u2vvPrVGDcybaDXsQZqQOctKdV4CJOFPoBQI8taHXNE'


class VoucherFetchWizard(models.TransientModel):
    _name = 'voucher.fetch.wizard'
    _description = 'Fetch Voucher Wizard'

    date_from = fields.Date(string='From Date', required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string='To Date', required=True, default=lambda self: date.today().replace(
        day=calendar.monthrange(date.today().year, date.today().month)[1]))

    def _get_api_token(self):
        try:
            resp = requests.post(
                f'{BASE_URL}/auth/token',
                json={
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get('access_token')
        except requests.exceptions.RequestException as e:
            raise UserError(_('API Authentication Failed.\n\nUnable to generate access token: %s') % e)

    def _fetch_journal_entries(self, token, target_date_from, target_date_to):
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        }
        page = 1
        page_size = 1000
        entries = []

        session = requests.Session()
        session.headers.update(headers)

        while True:
            try:
                resp = session.get(
                    f'{BASE_URL}/journal-entries',
                    params={
                        'date_from': target_date_from.strftime('%Y-%m-%d'),
                        'date_to': target_date_to.strftime('%Y-%m-%d'),
                        'page': page,
                        'page_size': page_size,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                raise UserError(
                    _('API Fetch Exception.\n\nFailed to retrieve journal entries on page %s: %s') % (page, e)
                )

            page_data = data.get('data', [])
            entries.extend(page_data)

            pagination = data.get('pagination', {})
            if not pagination.get('has_next'):
                break

            page += 1

        return entries

    def _create_failed_log(self, log_vals):
        with self.pool.cursor() as new_cr:
            new_env = api.Environment(new_cr, self.env.uid, self.env.context)
            new_env['api.fetch.log'].create(log_vals)
            new_cr.commit()

    def _process_and_create_jv(self, target_date_from, target_date_to):
        log_name = f"API Log / {target_date_from.strftime('%Y-%m-%d')} - {target_date_to.strftime('%Y-%m-%d')}"

        log_vals = {
            'name': log_name,
            'date_from': target_date_from,
            'date_to': target_date_to,
            'execution_time': fields.Datetime.now(),
        }

        try:
            token = self._get_api_token()
            entries = self._fetch_journal_entries(token, target_date_from, target_date_to)
            log_vals['total_retrieved'] = len(entries)

            if not entries:
                log_vals['status'] = 'warning'
                log_vals['error_message'] = '''
                <div class="card border-info shadow-sm">
                    <div class="card-body py-2 px-3 bg-light text-info fw-bold">
                        <i class="fa fa-info-circle me-2"/>No records fetched from API for the selected date range.
                    </div>
                </div>'''
                self.env['api.fetch.log'].create(log_vals)
                return self.env['account.move']

            existing_refs = set(
                self.env['account.move'].search_read(
                    [('state', '!=', 'cancel'), ('ref', '!=', False)],
                    ['ref']
                )
            )
            existing_ref_set = {str(r['ref']).strip() for r in existing_refs if r.get('ref')}

            new_entries = []
            skipped_count = 0

            for entry in entries:
                ref = str(
                    entry.get('reference') or
                    entry.get('entry_number') or
                    entry.get('id') or
                    ''
                ).strip()

                if ref and ref in existing_ref_set:
                    skipped_count += 1
                    continue
                new_entries.append(entry)

            log_vals['total_skipped'] = skipped_count

            if not new_entries:
                log_vals['status'] = 'warning'
                log_vals['total_created'] = 0
                log_vals['error_message'] = '''
                <div class="card border-info shadow-sm">
                    <div class="card-body py-2 px-3 bg-light text-info fw-bold">
                        <i class="fa fa-info-circle me-2"/>All fetched entries already exist in system.
                    </div>
                </div>'''
                log_record = self.env['api.fetch.log'].create(log_vals)
                log_record.write({'status': 'warning'})
                return self.env['account.move']

            active_codes = set()
            for entry in new_entries:
                for line in entry.get('lines', []):
                    code = str(line.get('account_code') or '').strip()
                    debit = float(line.get('debit', 0.0))
                    credit = float(line.get('credit', 0.0))
                    if code and (round(debit, 2) > 0 or round(credit, 2) > 0):
                        active_codes.add(code)

            if not active_codes:
                log_vals['status'] = 'warning'
                log_vals['error_message'] = '''
                <div class="card border-warning shadow-sm">
                    <div class="card-body py-2 px-3 bg-light text-warning fw-bold">
                        <i class="fa fa-exclamation-triangle me-2"/>Retrieved entries contained zero balance or valid debit/credit lines.
                    </div>
                </div>'''
                self.env['api.fetch.log'].create(log_vals)
                return self.env['account.move']

            accounts = self.env['account.account'].search([('api_account_code', 'in', list(active_codes))])
            account_map = {acc.api_account_code: acc.id for acc in accounts}

            missing_accounts = set()
            for entry in new_entries:
                for line in entry.get('lines', []):
                    code = str(line.get('account_code') or '').strip()
                    debit = float(line.get('debit', 0.0))
                    credit = float(line.get('credit', 0.0))
                    if code and (round(debit, 2) > 0 or round(credit, 2) > 0) and code not in account_map:
                        account_name = line.get('account_name', '')
                        missing_accounts.add(f'• Code: {code} | Name: {account_name}')

            if missing_accounts:
                items_html = ''.join(
                    [f'<div class="p-2 mb-1 bg-white border rounded text-danger fw-bold small">{acc}</div>' for acc in
                     missing_accounts])
                missing_msg = f'''
                <div class="p-3 bg-light border rounded shadow-sm">{items_html}</div>
                '''
                log_vals['status'] = 'failed'
                log_vals['unmapped_accounts_log'] = missing_msg
                log_vals['error_message'] = '''
                <div class="card border-danger shadow-sm">
                    <div class="card-body py-2 px-3 bg-light text-danger fw-bold">
                        <i class="fa fa-ban me-2"/>Execution halted due to unmapped accounts.
                    </div>
                </div>'''

                self._create_failed_log(log_vals)

                raise UserError(
                    _('Unmapped Accounts Detected.\n\nThe following external accounts are missing in Chart of Accounts:\n\n%s\n\nPlease map them before proceeding.') % '\n'.join(
                        missing_accounts)
                )

            glowsims_journal = self.env['account.journal'].search([('name', 'ilike', 'GLOWSIMS')], limit=1)

            if not glowsims_journal:
                log_vals['status'] = 'failed'
                log_vals['error_message'] = '''
                <div class="card border-danger shadow-sm">
                    <div class="card-body py-2 px-3 bg-light text-danger fw-bold">
                        <i class="fa fa-ban me-2"/>Journal with name 'GLOWSIMS' not found.
                    </div>
                </div>'''

                self._create_failed_log(log_vals)

                raise UserError(_('Configuration Error.\n\nNo journal found with the name \'GLOWSIMS\'.'))

            log_record = self.env['api.fetch.log'].create(log_vals)
            moves_to_create = []

            for entry in new_entries:
                move_lines = []

                entry_ref = str(
                    entry.get('reference') or
                    entry.get('entry_number') or
                    entry.get('id') or
                    ''
                ).strip()

                raw_date = entry.get('posting_date') or entry.get('created_at') or entry.get('date')
                if raw_date:
                    entry_date = str(raw_date).split('T')[0].split(' ')[0]
                else:
                    entry_date = target_date_to

                narration = entry.get('narration') or False

                for line in entry.get('lines', []):
                    code = str(line.get('account_code') or '').strip()
                    if not code:
                        continue

                    debit = round(float(line.get('debit', 0.0)), 2)
                    credit = round(float(line.get('credit', 0.0)), 2)

                    if debit == 0 and credit == 0:
                        continue

                    account_id = account_map.get(code)
                    if not account_id:
                        continue

                    line_name = line.get('description') or narration or False

                    move_lines.append((0, 0, {
                        'account_id': account_id,
                        'name': line_name,
                        'debit': debit,
                        'credit': credit,
                    }))

                if move_lines:
                    move_vals = {
                        'journal_id': glowsims_journal.id,
                        'date': entry_date,
                        'ref': entry_ref if entry_ref else False,
                        'narration': narration,
                        'is_api_fetched': True,
                        'api_fetch_log_id': log_record.id,
                        'line_ids': move_lines,
                    }
                    moves_to_create.append(move_vals)

            created_moves = self.env['account.move']
            if moves_to_create:
                created_moves = self.env['account.move'].create(moves_to_create)

            log_record.write({
                'status': 'success',
                'total_created': len(created_moves),
                'move_ids': [(6, 0, created_moves.ids)],
            })

            return created_moves

        except Exception as e:
            if log_vals.get('status') != 'failed':
                log_vals['status'] = 'failed'
                log_vals['error_message'] = f'''
                <div class="card border-danger shadow-sm">
                    <div class="card-body py-2 px-3 bg-light text-danger fw-bold">
                        <i class="fa fa-ban me-2"/>{str(e)}
                    </div>
                </div>'''
                self._create_failed_log(log_vals)
            raise

    def action_fetch_and_create_jv(self):
        journal_entries = self._process_and_create_jv(self.date_from, self.date_to)

        count = len(journal_entries)
        if count == 0:
            msg = _('Execution completed. No new Journal Entries created.')
        else:
            msg = _('Successfully fetched and created %s Journal Entries.') % count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('API Fetch Processing'),
                'message': msg,
                'type': 'success' if count > 0 else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def cron_fetch_previous_day_vouchers(self):
        yesterday = date.today() - timedelta(days=1)
        wizard = self.create({
            'date_from': yesterday,
            'date_to': yesterday,
        })
        wizard._process_and_create_jv(yesterday, yesterday)
