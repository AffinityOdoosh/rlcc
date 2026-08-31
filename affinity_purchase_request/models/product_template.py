from odoo import fields, models


class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    purchase_request = fields.Boolean(company_dependent=True,
                                      help="Check this box to generate Purchase Request instead of generating Requests For Quotation from procurement.")
