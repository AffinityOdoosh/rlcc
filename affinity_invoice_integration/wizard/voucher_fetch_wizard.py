import calendar
from collections import defaultdict
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
        existing_move = self.env['account.move'].search([
            ('voucher_date_from', '=', target_date_from),
            ('voucher_date_to', '=', target_date_to),
            ('state', '!=', 'cancel'),
        ], limit=1)

        if existing_move:
            raise UserError(
                _('Duplicate Entry Detected.\n\nA Journal Entry (%s) has already been created for the date range %s to %s.') % (
                    existing_move.name or _('Draft'),
                    target_date_from,
                    target_date_to
                ))

        token = self._get_api_token()
        entries = self._fetch_journal_entries(token, target_date_from, target_date_to)

        if not entries:
            return False

        summary = defaultdict(lambda: {'debit': 0.0, 'credit': 0.0, 'descriptions': set(), 'name': ''})

        for entry in entries:
            for line in entry.get('lines', []):
                code = str(line.get('account_code') or '').strip()
                if not code:
                    continue

                debit = float(line.get('debit', 0.0))
                credit = float(line.get('credit', 0.0))
                account_name = line.get('account_name', '')
                desc = line.get('description') or ''

                summary[code]['debit'] += debit
                summary[code]['credit'] += credit
                summary[code]['name'] = account_name
                if desc.strip():
                    summary[code]['descriptions'].add(desc.strip())

        active_codes = [
            code for code, values in summary.items()
            if round(values['debit'], 2) > 0 or round(values['credit'], 2) > 0
        ]

        if not active_codes:
            return False

        accounts = self.env['account.account'].search([('api_account_code', 'in', active_codes)])
        account_map = {acc.api_account_code: acc for acc in accounts}

        missing_accounts = [
            f"• Code: {code} | Name: {summary[code]['name']}"
            for code in active_codes if code not in account_map
        ]

        if missing_accounts:
            missing_msg = '\n'.join(missing_accounts)
            raise UserError(
                _('Unmapped Accounts Detected.\n\nThe following external accounts are missing in the Chart of Accounts mapping:\n\n%s\n\nPlease set the "API Account Code" on the respective accounts before proceeding.') % missing_msg)

        glowsims_journal = self.env['account.journal'].search([('name', 'ilike', 'glowsims')], limit=1)
        if not glowsims_journal:
            glowsims_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)

        if not glowsims_journal:
            raise UserError(
                _('Configuration Error.\n\nNo suitable General Journal was found to register the synchronized entries. Please configure a journal.'))

        move_lines = []
        for code in active_codes:
            values = summary[code]
            account = account_map[code]
            net_debit = round(values['debit'], 2)
            net_credit = round(values['credit'], 2)

            line_name = ' / '.join(values['descriptions']) if values['descriptions'] else False

            move_lines.append((0, 0, {
                'account_id': account.id,
                'name': line_name,
                'debit': net_debit,
                'credit': net_credit,
            }))

        move_vals = {
            'journal_id': glowsims_journal.id,
            'date': target_date_to,
            'ref': f'Accumulated JV Sync ({target_date_from} to {target_date_to})',
            'voucher_date_from': target_date_from,
            'voucher_date_to': target_date_to,
            'line_ids': move_lines,
        }

        return self.env['account.move'].create(move_vals)

    def action_fetch_and_create_jv(self):
        journal_entry = self._process_and_create_jv(self.date_from, self.date_to)
        if not journal_entry:
            raise UserError(
                _('No Data Found.\n\nNo active transactions or non-zero balances were retrieved for the selected date range (%s to %s).') % (
                    self.date_from, self.date_to))

        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': journal_entry.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def cron_fetch_previous_day_vouchers(self):
        yesterday = date.today() - timedelta(days=1)
        wizard = self.create({
            'date_from': yesterday,
            'date_to': yesterday,
        })
        wizard._process_and_create_jv(yesterday, yesterday)
