from odoo import models


class StockWarehouseOrderpointInherit(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _quantity_in_progress(self):
        res = super()._quantity_in_progress()
        for prline in self.env["purchase.request.line"].search([
            ("request_id.state", "in", ("draft", "approved", "to_approve", "in_progress"),),
            ("orderpoint_id", "in", self.ids),
            ("purchase_state", "=", False),
        ]):
            res[prline.orderpoint_id.id] += prline.product_uom_id._compute_quantity(prline.product_qty,
                                                                                    prline.orderpoint_id.product_uom,
                                                                                    round=False)
        return res
