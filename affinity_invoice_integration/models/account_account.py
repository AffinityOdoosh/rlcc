import requests
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

BASE_URL = 'https://rlcc.glowsims.com/api/finance/v1'
CLIENT_ID = 'odoo_integration'
CLIENT_SECRET = 'u2vvPrVGDcybaDXsQZqQOctKdV4CJOFPoBQI8taHXNE'


class AccountAccount(models.Model):
    _inherit = 'account.account'

    api_account_code = fields.Char(string='API Code', index=True, copy=False,
                                   help='External API account code used for synchronization.')
    api_account_name = fields.Char(string='API Account Name', readonly=True, copy=False)

    _sql_constraints = [(
        'api_account_code_unique',
        'unique(api_account_code)',
        'The API Account Code must be unique across Chart of Accounts!'
    )]

    @api.constrains('api_account_code')
    def _check_api_account_code_unique(self):
        for record in self:
            if record.api_account_code:
                domain = [
                    ('api_account_code', '=', record.api_account_code),
                    ('id', '!=', record.id)
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_('The API Account Code must be unique across Chart of Accounts!'))

    @api.onchange('api_account_code')
    def _onchange_api_account_code(self):
        if not self.api_account_code:
            self.api_account_name = False
            return
        fetched_name = self._fetch_api_account_name(self.api_account_code)
        if fetched_name:
            self.api_account_name = fetched_name

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
        except requests.exceptions.RequestException:
            return False

    def _fetch_api_account_name(self, code):
        token = self._get_api_token()
        if not token:
            return False

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        }
        page = 1
        page_size = 1000

        while True:
            try:
                resp = requests.get(
                    f'{BASE_URL}/chart-of-accounts',
                    headers=headers,
                    params={
                        'page': page,
                        'page_size': page_size,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException:
                return False

            accounts_data = data.get('data', [])
            for acc in accounts_data:
                if str(acc.get('account_code') or '').strip() == str(code).strip():
                    return acc.get('account_name')

            pagination = data.get('pagination', {})
            if not pagination.get('has_next'):
                break

            page += 1

        return False
