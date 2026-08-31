from odoo import api, fields, models


class PurchaseRequestLineMakePurchaseOrderItem(models.TransientModel):
    _name = 'purchase.request.line.make.purchase.order.item'
    _description = 'Purchase Request Line Make Purchase Order Item'

    wiz_id = fields.Many2one(comodel_name='purchase.request.line.make.purchase.order', string='Wizard', required=True,
                             ondelete='cascade', readonly=True)
    line_id = fields.Many2one(comodel_name='purchase.request.line', string='Purchase Request Line')
    request_id = fields.Many2one(comodel_name='purchase.request', related='line_id.request_id',
                                 string='Purchase Request', readonly=False)
    product_id = fields.Many2one(comodel_name='product.product', string='Product', related='line_id.product_id',
                                 readonly=False)
    name = fields.Char(string='Description', required=True)
    product_qty = fields.Float(string='Qty.', digits='Product Unit of Measure')
    product_uom_id = fields.Many2one(comodel_name='uom.uom', string='UoM', required=True)
    keep_description = fields.Boolean(string='Retain Custom Description',
                                      help='Set true if you want to keep the descriptions provided in the wizard in the new PO.', )

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            if not self.keep_description:
                name = self.product_id.name
            code = self.product_id.code
            sup_info_id = self.env['product.supplierinfo'].search([
                '|',
                ('product_id', '=', self.product_id.id),
                ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
                ('partner_id', '=', self.wiz_id.supplier_id.id),
            ])
            if sup_info_id:
                p_code = sup_info_id[0].product_code
                p_name = sup_info_id[0].product_name
                name = f'[{p_code if p_code else code}] {p_name if p_name else name}'
            else:
                if code:
                    name = f'[{code}] {self.name if self.keep_description else name}'
            if self.product_id.description_purchase and not self.keep_description:
                name += '\n' + self.product_id.description_purchase
            self.product_uom_id = self.product_id.uom_id.id
            if name:
                self.name = name
