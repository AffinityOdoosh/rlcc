from markupsafe import Markup

from odoo import _, models, fields, exceptions
from odoo.tools import html_escape


class PurchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    purchase_request_id = fields.Many2one(comodel_name='purchase.request', string='Purchase Request',
                                          ondelete='set null')

    def _purchase_request_confirm_message_content(self, request, request_dict=None):
        self.ensure_one()
        if not request_dict:
            request_dict = {}
        title = _('Order confirmation %(po_name)s for your Request %(pr_name)s') % {
            'po_name': self.name,
            'pr_name': request.name,
        }
        message = f'<h3>{title}</h3><ul>'
        message += _(
            'The following requested items from Purchase Request %(pr_name)s '
            'have now been confirmed in Purchase Order %(po_name)s:',
            po_name=self.name,
            pr_name=request.name,
        )

        for line in request_dict.values():
            message += _(
                '<li><b>%(prl_name)s</b>: Ordered quantity %(prl_qty)s %(prl_uom)s, '
                'Planned date %(prl_date_planned)s</li>'
            ) % {
                           'prl_name': html_escape(line['name']),
                           'prl_qty': line['product_qty'],
                           'prl_uom': line['product_uom'],
                           'prl_date_planned': line['date_planned'],
                       }
        message += '</ul>'
        return message

    def _purchase_request_confirm_message(self):
        request_obj = self.env['purchase.request']
        for po in self:
            requests_dict = {}
            for line in po.order_line:
                for request_line in line.sudo().purchase_request_lines:
                    request_id = request_line.request_id.id
                    if request_id not in requests_dict:
                        requests_dict[request_id] = {}
                    date_planned = line.date_planned
                    data = {
                        'name': request_line.name,
                        'product_qty': line.product_qty,
                        'product_uom': line.product_uom.name,
                        'date_planned': date_planned,
                    }
                    requests_dict[request_id][request_line.id] = data
            for request_id in requests_dict:
                request = request_obj.sudo().browse(request_id)
                message = po._purchase_request_confirm_message_content(
                    request, requests_dict[request_id]
                )
                request.message_post(
                    body=Markup(message),
                    subtype_id=self.env.ref(
                        'affinity_purchase_request.mt_request_po_confirmed'
                    ).id,
                )
        return True

    def _purchase_request_line_check(self):
        for po in self:
            for line in po.order_line:
                for request_line in line.purchase_request_lines:
                    if request_line.sudo().purchase_state == 'done':
                        raise exceptions.UserError(
                            _('Purchase Request %s has already been completed')
                            % (request_line.request_id.name)
                        )
        return True

    def button_confirm(self):
        self._purchase_request_line_check()
        res = super().button_confirm()
        self._purchase_request_confirm_message()
        return res

    def unlink(self):
        alloc_to_unlink = self.env['purchase.request.allocation']
        for rec in self:
            for alloc in (
                    rec.order_line.mapped('purchase_request_lines')
                            .mapped('purchase_request_allocation_ids')
                            .filtered(
                        lambda alloc, rec=rec: alloc.purchase_line_id.order_id.id == rec.id
                    )
            ):
                alloc_to_unlink += alloc
        res = super().unlink()
        alloc_to_unlink.unlink()
        return res
