from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import html_escape


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    purchase_request_lines = fields.Many2many(comodel_name="purchase.request.line",
                                              relation="purchase_request_purchase_order_line_rel",
                                              column1="purchase_order_line_id", column2="purchase_request_line_id",
                                              readonly=True, copy=False, )
    purchase_request_allocation_ids = fields.One2many(comodel_name="purchase.request.allocation",
                                                      inverse_name="purchase_line_id",
                                                      string="Purchase Request Allocation", copy=False, )

    def action_open_request_line_tree_view(self):
        request_line_ids = []
        for line in self:
            request_line_ids += line.purchase_request_lines.ids

        domain = [("id", "in", request_line_ids)]

        return {
            "name": _("Purchase Request Lines"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.request.line",
            "view_mode": "list,form",
            "domain": domain,
        }

    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        val = super()._prepare_stock_moves(picking)
        all_list = []
        for v in val:
            all_ids = self.env["purchase.request.allocation"].search(
                [("purchase_line_id", "=", v["purchase_line_id"])]
            )
            for all_id in all_ids:
                all_list.append((4, all_id.id))
            v["purchase_request_allocation_ids"] = all_list
        return val

    def update_service_allocations(self, prev_qty_received):
        for rec in self:
            allocation = self.env["purchase.request.allocation"].search(
                [
                    ("purchase_line_id", "=", rec.id),
                    ("purchase_line_id.product_id.type", "=", "service"),
                ]
            )
            if not allocation:
                return
            qty_left = rec.qty_received - prev_qty_received
            for alloc in allocation:
                allocated_product_qty = alloc.allocated_product_qty
                if not qty_left:
                    alloc.purchase_request_line_id._compute_qty()
                    break
                if alloc.open_product_qty <= qty_left:
                    allocated_product_qty += alloc.open_product_qty
                    qty_left -= alloc.open_product_qty
                    alloc._notify_allocation(alloc.open_product_qty)
                else:
                    allocated_product_qty += qty_left
                    alloc._notify_allocation(qty_left)
                    qty_left = 0
                alloc.write({"allocated_product_qty": allocated_product_qty})

                message_data = self._prepare_request_message_data(
                    alloc, alloc.purchase_request_line_id, allocated_product_qty
                )
                message = self._purchase_request_confirm_done_message_content(
                    message_data
                )
                alloc.purchase_request_line_id.request_id.message_post(
                    body=Markup(message),
                    subtype_id=self.env.ref("mail.mt_note").id,
                )

                alloc.purchase_request_line_id._compute_qty()
        return True

    @api.model
    def _purchase_request_confirm_done_message_content(self, message_data):
        title = _("Service confirmation for Request {request_name}").format(
            request_name=message_data["request_name"]
        )

        message_body = _(
            "The following requested services from Purchase Request {request_name} "
            "requested by {requestor} have now been received:"
        ).format(
            request_name=message_data["request_name"],
            requestor=message_data["requestor"],
        )

        product_line = Markup(
            "<ul><li><b>{}</b>: " + _("Received quantity") + " {} {}</li></ul>"
        ).format(
            html_escape(message_data["product_name"]),
            message_data["product_qty"],
            html_escape(message_data["product_uom"]),
        )

        return Markup("<h3>{}</h3>{}{}").format(title, message_body, product_line)

    def _prepare_request_message_data(self, alloc, request_line, allocated_qty):
        return {
            "request_name": request_line.request_id.name,
            "product_name": request_line.product_id.display_name,
            "product_qty": allocated_qty,
            "product_uom": alloc.product_uom_id.name,
            "requestor": request_line.request_id.requested_by.partner_id.name,
        }

    def write(self, vals):
        prev_qty_received = {}
        if vals.get("qty_received", False):
            service_lines = self.filtered(
                lambda line: line.product_id.type == "service"
            )
            for line in service_lines:
                prev_qty_received[line.id] = line.qty_received
        res = super().write(vals)
        if prev_qty_received:
            for line in service_lines:
                line.update_service_allocations(prev_qty_received[line.id])
        return res
