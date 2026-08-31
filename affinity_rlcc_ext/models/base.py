from odoo import models, tools


class BaseInherit(models.AbstractModel):
    _inherit = 'base'

    def is_html_field_populated(self, field_name):
        self.ensure_one()
        html_content = getattr(self, field_name, False)
        if not html_content:
            return False
        return bool(tools.html2plaintext(html_content).strip())
