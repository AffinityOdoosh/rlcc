import calendar
from collections import defaultdict
from datetime import date
import requests

from odoo import models, fields
from odoo.exceptions import UserError

BASE_URL = "https://rlcc.glowsims.com/api/finance/v1"
CLIENT_ID = "odoo_integration"
CLIENT_SECRET = "u2vvPrVGDcybaDXsQZqQOctKdV4CJOFPoBQI8taHXNE"


class VoucherFetchWizard(models.TransientModel):
    _name = 'voucher.fetch.wizard'
    _description = 'Fetch Voucher Wizard'

    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=lambda self: date.today().replace(
            day=calendar.monthrange(date.today().year, date.today().month)[1]
        )
    )

    def _get_api_token(self):
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/token",
                json={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
        except requests.exceptions.RequestException as e:
            raise UserError(f"❌ Token generation failed: {e}")

    def _fetch_journal_entries(self, token):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        page = 1
        page_size = 1000
        entries = []

        while True:
            try:
                resp = requests.get(
                    f"{BASE_URL}/journal-entries",
                    headers=headers,
                    params={
                        "date_from": self.date_from.strftime('%Y-%m-%d'),
                        "date_to": self.date_to.strftime('%Y-%m-%d'),
                        "page": page,
                        "page_size": page_size,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                raise UserError(f"❌ Request failed on page {page}: {e}")

            page_data = data.get("data", [])
            entries.extend(page_data)

            pagination = data.get("pagination", {})
            if not pagination.get("has_next"):
                break

            page += 1

        return entries

    def action_fetch_and_create_jv(self):
        token = self._get_api_token()
        entries = self._fetch_journal_entries(token)

        if not entries:
            raise UserError('No journal entries found for the selected date range.')

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

        account_codes = list(summary.keys())

        accounts = self.env['account.account'].search([('api_account_code', 'in', account_codes)])
        account_map = {acc.api_account_code: acc for acc in accounts}

        missing_accounts = [
            f"• Code: {code} | Name: {summary[code]['name']}"
            for code in account_codes if code not in account_map
        ]

        if missing_accounts:
            missing_msg = "\n".join(missing_accounts)
            raise UserError(
                f"The following accounts from the API were not mapped in Chart of Accounts:\n\n{missing_msg}\n\n"
                "Please set the 'API Account Code' field on these accounts in Chart of Accounts before fetching."
            )

        glowsims_journal = self.env['account.journal'].search([('name', 'ilike', 'glowsims')], limit=1)
        if not glowsims_journal:
            glowsims_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)

        if not glowsims_journal:
            raise UserError('No matching journal found in Odoo. Please configure a Journal first.')

        move_lines = []
        for code, values in summary.items():
            account = account_map[code]
            net_debit = round(values['debit'], 2)
            net_credit = round(values['credit'], 2)

            if net_debit > 0 or net_credit > 0:
                line_name = " / ".join(values['descriptions']) if values['descriptions'] else False

                move_lines.append((0, 0, {
                    'account_id': account.id,
                    'name': line_name,
                    'debit': net_debit,
                    'credit': net_credit,
                }))

        if not move_lines:
            raise UserError('No valid line amounts to create a Journal Entry.')

        move_vals = {
            'journal_id': glowsims_journal.id,
            'date': self.date_to,
            'ref': f"Accumulated JV Sync ({self.date_from} to {self.date_to})",
            'line_ids': move_lines,
        }

        journal_entry = self.env['account.move'].create(move_vals)

        return {
            'name': 'Journal Entry',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': journal_entry.id,
            'view_mode': 'form',
            'target': 'current',
        }
