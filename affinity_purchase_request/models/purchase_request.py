from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _mail_post_access = 'read'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    @api.model
    def _company_get(self):
        return self.env['res.company'].browse(self.env.company.id)

    @api.model
    def _get_default_requested_by(self):
        return self.env['res.users'].browse(self.env.uid)

    @api.model
    def _get_default_name(self):
        return self.env['ir.sequence'].next_by_code('purchase.request')

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.company.id
        types = type_obj.search([
            ('code', '=', 'incoming'),
            ('warehouse_id.company_id', '=', company_id),
        ])
        if not types:
            types = type_obj.search([
                ('code', '=', 'incoming'),
                ('warehouse_id', '=', False),
            ])
        return types[:1]

    @api.depends('state')
    def _compute_is_editable(self):
        for rec in self:
            if rec.state in ('cancel', 'approved'):
                rec.is_editable = False
            else:
                rec.is_editable = True

    name = fields.Char(string='Reference', required=True, default=lambda self: _('New'), tracking=True, readonly=True)
    origin = fields.Char(string='Source Document')
    date = fields.Date(string='Request Date', help='Date when the user initiated the request.',
                       default=fields.Date.context_today, tracking=True)
    approved_date = fields.Datetime(string='Approved On', help='Date and time when the request was approved.',
                                    tracking=True)
    requested_by = fields.Many2one(comodel_name='res.users', string='Requested By', required=True, copy=False,
                                   tracking=True, default=_get_default_requested_by, index=True)
    location_id = fields.Many2one(comodel_name='stock.location', string='Destination Location',
                                  related='requested_by.location_id', domain="[('usage', '=', 'internal')]")
    assigned_to = fields.Many2one(comodel_name='res.users', string='Approver', tracking=True, index=True,
                                  related='location_id.manager_id')
    description = fields.Text(string='Description')
    company_id = fields.Many2one(comodel_name='res.company', string='Company', required=False, default=_company_get,
                                 tracking=True)
    line_ids = fields.One2many(comodel_name='purchase.request.line', inverse_name='request_id',
                               string='Products to Purchase', readonly=False, copy=True, tracking=True)
    product_id = fields.Many2one(comodel_name='product.product', related='line_ids.product_id', string='Product',
                                 readonly=True)
    state = fields.Selection(selection=[('draft', 'Draft'), ('approved', 'Approved'), ('cancel', 'Cancelled')],
                             string='Status', index=True, tracking=True, required=True, copy=False, default='draft')
    is_editable = fields.Boolean(compute='_compute_is_editable', readonly=True)
    picking_type_id = fields.Many2one(comodel_name='stock.picking.type', string='Deliver To', required=True,
                                      default=_default_picking_type)
    group_id = fields.Many2one(comodel_name='procurement.group', string='Procurement Group', copy=False, index=True)
    line_count = fields.Integer(string='Line Count', compute='_compute_line_count', readonly=True)
    move_count = fields.Integer(string='Stock Move Count', compute='_compute_move_count', readonly=True)
    purchase_count = fields.Integer(string='Purchases Count', compute='_compute_purchase_count', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute='_compute_amounts', store=True,
                                     currency_field='currency_id')
    amount_tax = fields.Monetary(string='Taxes', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_total = fields.Monetary(string='Total', compute='_compute_amounts', store=True, currency_field='currency_id')
    estimated_cost = fields.Monetary(compute='_compute_estimated_cost', string='Total Estimated Cost', store=True)

    notes = fields.Html(string='Terms and Conditions')
    tax_totals = fields.Binary(compute='_compute_tax_totals', exportable=False)

    @api.depends('line_ids.estimated_cost')
    def _compute_estimated_cost(self):
        for rec in self:
            rec.estimated_cost = sum(rec.line_ids.mapped('estimated_cost'))

    @api.depends('line_ids.estimated_cost')
    def _compute_amounts(self):
        for req in self:
            req.amount_untaxed = sum(line.estimated_cost for line in req.line_ids)
            req.amount_tax = 0.0
            req.amount_total = req.amount_untaxed + req.amount_tax

    @api.depends_context('lang')
    @api.depends('line_ids.estimated_cost', 'line_ids.product_qty', 'currency_id', 'company_id')
    def _compute_tax_totals(self):
        AccountTax = self.env['account.tax']
        for req in self:
            company = req.company_id or self.env.company
            base_lines = []
            for line in req.line_ids:
                taxes = getattr(line, 'tax_id', False) or getattr(line, 'taxes_id', False) or self.env['account.tax']
                base_lines.append(AccountTax._prepare_base_line_for_taxes_computation(
                    line,
                    price_unit=line.estimated_cost / line.product_qty if line.product_qty else line.estimated_cost,
                    quantity=line.product_qty or 1.0,
                    taxes=taxes,
                    currency=req.currency_id or company.currency_id,
                ))
            if base_lines:
                AccountTax._add_tax_details_in_base_lines(base_lines, company)
                AccountTax._round_base_lines_tax_details(base_lines, company)
                req.tax_totals = AccountTax._get_tax_totals_summary(
                    base_lines=base_lines,
                    currency=req.currency_id or company.currency_id,
                    company=company,
                )
            else:
                req.tax_totals = False

    @api.depends('line_ids')
    def _compute_purchase_count(self):
        for rec in self:
            rec.purchase_count = len(rec.mapped('line_ids.purchase_lines.order_id'))

    def action_view_purchase_order(self):
        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_rfq')
        lines = self.mapped('line_ids.purchase_lines.order_id')
        if len(lines) > 1:
            action['domain'] = [('id', 'in', lines.ids)]
        elif lines:
            action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            action['res_id'] = lines.id
        return action

    @api.depends('line_ids')
    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.mapped('line_ids.purchase_request_allocation_ids.stock_move_id'))

    def action_view_stock_picking(self):
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_all')
        action['context'] = {}
        lines = self.mapped('line_ids.purchase_request_allocation_ids.stock_move_id.picking_id')
        if len(lines) > 1:
            action['domain'] = [('id', 'in', lines.ids)]
        elif lines:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = lines.id
        return action

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.mapped('line_ids'))

    def action_view_purchase_request_line(self):
        action = self.env.ref('affinity_purchase_request.purchase_request_line_form_action').sudo().read()[0]
        lines = self.mapped('line_ids')
        if len(lines) > 1:
            action['domain'] = [('id', 'in', lines.ids)]
        elif lines:
            action['views'] = [(self.env.ref('affinity_purchase_request.purchase_request_line_form').id, 'form')]
            action['res_id'] = lines.ids[0]
        return action

    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({'state': 'draft', 'name': self._get_default_name()})
        return super().copy(default)

    @api.model
    def _get_partner_id(self, request):
        user_id = request.assigned_to or self.env.user
        return user_id.partner_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self._get_default_name()
        requests = super().create(vals_list)
        for vals, request in zip(vals_list, requests, strict=True):
            if vals.get('assigned_to'):
                partner_id = self._get_partner_id(request)
                request.message_subscribe(partner_ids=[partner_id])
        return requests

    def write(self, vals):
        res = super().write(vals)
        for request in self:
            if vals.get('assigned_to'):
                partner_id = self._get_partner_id(request)
                request.message_subscribe(partner_ids=[partner_id])
        return res

    def _can_be_deleted(self):
        self.ensure_one()
        return self.state == 'draft'

    def unlink(self):
        for request in self:
            if not request._can_be_deleted():
                raise UserError(_('You can only delete purchase requests in draft state.'))
        return super().unlink()

    def action_draft(self):
        self.mapped('line_ids').do_uncancel()
        return self.write({'state': 'draft', 'approved_date': False})

    def action_approved(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_('You cannot approve a request without any lines.'))

            invalid_lines = rec.line_ids.filtered(lambda l: not l.product_qty or l.product_qty <= 0)
            if invalid_lines:
                raise ValidationError(
                    _('You cannot approve this request because some lines have zero or invalid quantity.'))

            rec.write({
                'state': 'approved',
                'approved_date': fields.Datetime.now(),
            })

    def action_cancel(self):
        return self.write({'state': 'cancel'})
