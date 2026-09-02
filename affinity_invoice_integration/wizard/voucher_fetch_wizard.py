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

        while True:
            try:
                resp = requests.get(
                    f'{BASE_URL}/journal-entries',
                    headers=headers,
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
                    _('API Fetch Exception.\n\nFailed to retrieve journal entries on page %s: %s') % (page, e))

            page_data = data.get('data', [])
            entries.extend(page_data)

            pagination = data.get('pagination', {})
            if not pagination.get('has_next'):
                break

            page += 1

        return entries

    def _process_and_create_jv(self, target_date_from, target_date_to):
        log_vals = {
            'date_from': target_date_from,
            'date_to': target_date_to,
            'execution_time': fields.Datetime.now(),
        }

        try:
            token = self._get_api_token()
            entries = self._fetch_journal_entries(token, target_date_from, target_date_to)
            log_vals['total_retrieved'] = len(entries)

            if not entries:
                log_vals['status'] = 'success'
                log_vals['error_message'] = 'No records fetched from API for the selected date range.'
                self.env['api.fetch.log'].create(log_vals)
                return self.env['account.move']

            existing_moves = self.env['account.move'].search([
                ('state', '!=', 'cancel'),
                ('ref', '!=', False),
            ])
            existing_refs = {str(ref).strip() for ref in existing_moves.mapped('ref')}

            new_entries = []
            skipped_count = 0

            for entry in entries:
                ref = str(
                    entry.get('reference') or
                    entry.get('voucher_no') or
                    entry.get('name') or
                    entry.get('id') or
                    entry.get('voucher_id') or
                    ''
                ).strip()

                if ref and ref in existing_refs:
                    skipped_count += 1
                    continue
                new_entries.append(entry)

            log_vals['total_skipped'] = skipped_count

            if not new_entries:
                log_vals['status'] = 'success'
                log_vals['total_created'] = 0
                log_vals['error_message'] = 'All fetched entries already exist in system.'
                self.env['api.fetch.log'].create(log_vals)
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
                log_vals['error_message'] = 'Retrieved entries contained zero balance or valid debit/credit lines.'
                self.env['api.fetch.log'].create(log_vals)
                return self.env['account.move']

            accounts = self.env['account.account'].search([('api_account_code', 'in', list(active_codes))])
            account_map = {acc.api_account_code: acc for acc in accounts}

            missing_accounts = set()
            for entry in new_entries:
                for line in entry.get('lines', []):
                    code = str(line.get('account_code') or '').strip()
                    debit = float(line.get('debit', 0.0))
                    credit = float(line.get('credit', 0.0))
                    if code and (round(debit, 2) > 0 or round(credit, 2) > 0) and code not in account_map:
                        account_name = line.get('account_name', '')
                        missing_accounts.add(f"• Code: {code} | Name: {account_name}")

            if missing_accounts:
                missing_msg = '\n'.join(missing_accounts)
                log_vals['status'] = 'failed'
                log_vals['unmapped_accounts_log'] = missing_msg
                log_vals['error_message'] = 'Execution halted due to unmapped accounts.'
                self.env['api.fetch.log'].create(log_vals)
                raise UserError(
                    _('Unmapped Accounts Detected.\n\nThe following external accounts are missing in Chart of Accounts:\n\n%s\n\nPlease map them before proceeding.') % missing_msg)

            glowsims_journal = self.env['account.journal'].search([('name', 'ilike', 'GLOWSIMS')], limit=1)

            if not glowsims_journal:
                log_vals['status'] = 'failed'
                log_vals['error_message'] = 'Journal with name "GLOWSIMS" not found.'
                self.env['api.fetch.log'].create(log_vals)
                raise UserError(_('Configuration Error.\n\nNo journal found with the name "GLOWSIMS".'))

            created_moves = self.env['account.move']

            for entry in new_entries:
                move_lines = []

                entry_ref = str(
                    entry.get('reference') or
                    entry.get('voucher_no') or
                    entry.get('name') or
                    entry.get('id') or
                    entry.get('voucher_id') or
                    ''
                ).strip()

                entry_date = entry.get('date') or entry.get('voucher_date') or entry.get('created_at') or target_date_to

                for line in entry.get('lines', []):
                    code = str(line.get('account_code') or '').strip()
                    if not code:
                        continue

                    debit = round(float(line.get('debit', 0.0)), 2)
                    credit = round(float(line.get('credit', 0.0)), 2)

                    if debit == 0 and credit == 0:
                        continue

                    account = account_map.get(code)
                    if not account:
                        continue

                    line_name = line.get('description') or False

                    move_lines.append((0, 0, {
                        'account_id': account.id,
                        'name': line_name,
                        'debit': debit,
                        'credit': credit,
                    }))

                if move_lines:
                    move_vals = {
                        'journal_id': glowsims_journal.id,
                        'date': entry_date,
                        'ref': entry_ref if entry_ref else False,
                        'line_ids': move_lines,
                    }
                    move = self.env['account.move'].create(move_vals)
                    created_moves |= move
                    if entry_ref:
                        existing_refs.add(entry_ref)

            log_vals['status'] = 'success'
            log_vals['total_created'] = len(created_moves)
            log_vals['move_ids'] = [(6, 0, created_moves.ids)]
            self.env['api.fetch.log'].create(log_vals)

            return created_moves

        except Exception as e:
            if log_vals.get('status') != 'failed':
                log_vals['status'] = 'failed'
                log_vals['error_message'] = str(e)
                self.env['api.fetch.log'].create(log_vals)
            raise e

    def action_fetch_and_create_jv(self):
        journal_entries = self._process_and_create_jv(self.date_from, self.date_to)

        count = len(journal_entries)
        if count == 0:
            msg = _("Execution completed. No new Journal Entries created.")
        else:
            msg = _("Successfully fetched and created %s Journal Entries.") % count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('API Fetch Processing'),
                'message': msg,
                'type': 'success' if count > 0 else 'warning',
                'sticky': False,
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
