from odoo import api, fields, models
from odoo.exceptions import UserError

REQUEST_STATES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rfq_created", "RFQ Created"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
]

PROCUREMENT_GROUP = "retail_base.group_procurement_manager"


class RetailPurchaseRequest(models.Model):
    _name = "retail.purchase.request"
    _description = "Retail Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True, default="New"
    )
    state = fields.Selection(
        selection=REQUEST_STATES,
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    requestor_id = fields.Many2one(
        comodel_name="res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    preferred_vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Preferred Supplier",
        domain="[('is_company', '=', True)]",
    )
    date_required = fields.Date(string="Required By")
    justification = fields.Text(
        help="Why this purchase is needed. Reviewed by procurement before approval."
    )
    line_ids = fields.One2many(
        comodel_name="retail.purchase.request.line",
        inverse_name="request_id",
        string="Products",
        copy=True,
    )
    purchase_order_ids = fields.One2many(
        comodel_name="purchase.order",
        inverse_name="retail_request_id",
        string="Requests for Quotation",
        readonly=True,
    )
    order_count = fields.Integer(compute="_compute_order_count")
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", readonly=True
    )
    amount_estimated = fields.Monetary(
        compute="_compute_amount_estimated",
        currency_field="currency_id",
        string="Estimated Total",
        store=True,
    )

    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    rejected_by_id = fields.Many2one("res.users", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("line_ids.subtotal")
    def _compute_amount_estimated(self):
        for request in self:
            request.amount_estimated = sum(request.line_ids.mapped("subtotal"))

    @api.depends("purchase_order_ids")
    def _compute_order_count(self):
        for request in self:
            request.order_count = len(request.purchase_order_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("retail.purchase.request")
                    or "New"
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_procurement_rights(self):
        if not self.env.user.has_group(PROCUREMENT_GROUP):
            raise UserError(
                self.env._(
                    "Only a Procurement Manager may approve or reject purchase requests."
                )
            )

    def _notify_procurement(self, body):
        self.ensure_one()
        group = self.env.ref(PROCUREMENT_GROUP, raise_if_not_found=False)
        partners = group.users.partner_id if group else self.env["res.partner"]
        if not partners:
            return False
        return self.message_post(
            body=body, partner_ids=partners.ids, subtype_xmlid="mail.mt_comment"
        )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(
                    self.env._("Only draft requests can be submitted.")
                )
            if not request.line_ids:
                raise UserError(
                    self.env._("Add at least one product before submitting.")
                )
        self.write({"state": "submitted"})
        for request in self:
            request._notify_procurement(
                self.env._(
                    "Purchase request %(name)s awaits procurement review "
                    "(estimated %(amount)s).",
                    name=request.name,
                    amount=request.amount_estimated,
                )
            )
        return True

    def action_approve(self):
        self._check_procurement_rights()
        for request in self:
            if request.state != "submitted":
                raise UserError(
                    self.env._("Only submitted requests can be approved.")
                )
        self.write(
            {
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            }
        )
        return True

    def action_reject_with_reason(self, reason):
        self._check_procurement_rights()
        for request in self:
            if request.state not in ("submitted", "approved"):
                raise UserError(
                    self.env._("Only submitted or approved requests can be rejected.")
                )
        self.write(
            {
                "state": "rejected",
                "rejection_reason": reason,
                "rejected_by_id": self.env.user.id,
            }
        )
        return True

    def action_reject(self):
        """Open the rejection wizard, reusing the requisition wizard pattern."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reject Purchase Request"),
            "res_model": "retail.purchase.request.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def action_cancel(self):
        for request in self:
            if request.state not in ("draft", "submitted"):
                raise UserError(
                    self.env._(
                        "Only draft or submitted requests can be cancelled."
                    )
                )
        self.write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        for request in self:
            if request.state not in ("rejected", "cancelled"):
                raise UserError(
                    self.env._(
                        "Only rejected or cancelled requests can be reset to draft."
                    )
                )
        self.write(
            {"state": "draft", "rejection_reason": False, "rejected_by_id": False}
        )
        return True

    def action_create_rfq(self):
        """US-PRQ-02: turn an approved request into a draft purchase order."""
        self._check_procurement_rights()
        for request in self:
            if request.state != "approved":
                raise UserError(
                    self.env._(
                        "Only approved requests can be turned into an RFQ. "
                        "Request %s is not approved.",
                        request.name,
                    )
                )
            if not request.preferred_vendor_id:
                raise UserError(
                    self.env._(
                        "Set a preferred supplier on %s before creating an RFQ.",
                        request.name,
                    )
                )
            request._create_rfq()
        self.write({"state": "rfq_created"})
        return True

    def _create_rfq(self):
        self.ensure_one()
        return self.env["purchase.order"].create(
            {
                "partner_id": self.preferred_vendor_id.id,
                "origin": self.name,
                "retail_request_id": self.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "product_qty": line.qty_requested,
                            "product_uom": line.product_uom_id.id,
                            "price_unit": line.estimated_price,
                            "name": line.product_id.display_name,
                            "date_planned": fields.Datetime.now(),
                        },
                    )
                    for line in self.line_ids
                ],
            }
        )

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Requests for Quotation"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("retail_request_id", "=", self.id)],
        }


class RetailPurchaseRequestLine(models.Model):
    _name = "retail.purchase.request.line"
    _description = "Retail Purchase Request Line"

    request_id = fields.Many2one(
        comodel_name="retail.purchase.request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product", string="Product", required=True
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
    )
    qty_requested = fields.Float(
        string="Quantity", default=1.0, digits="Product Unit of Measure"
    )
    estimated_price = fields.Monetary(
        string="Estimated Unit Price",
        currency_field="currency_id",
        compute="_compute_estimated_price",
        store=True,
        readonly=False,
    )
    subtotal = fields.Monetary(
        compute="_compute_subtotal", currency_field="currency_id", store=True
    )
    currency_id = fields.Many2one(
        related="request_id.currency_id", readonly=True
    )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    @api.depends("product_id")
    def _compute_estimated_price(self):
        for line in self:
            line.estimated_price = line.product_id.standard_price

    @api.depends("qty_requested", "estimated_price")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty_requested * line.estimated_price
