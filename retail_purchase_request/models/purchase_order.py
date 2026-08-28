from odoo import api, fields, models
from odoo.exceptions import UserError


class RetailPurchaseApproval(models.Model):
    _name = "retail.purchase.approval"
    _description = "Purchase Order Approval"
    _order = "approval_date desc, id desc"

    order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Purchase Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Approved As",
        required=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Approved By",
        required=True,
        default=lambda self: self.env.user,
    )
    approval_date = fields.Datetime(default=fields.Datetime.now, required=True)
    amount_approved = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="order_id.currency_id", readonly=True)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    retail_request_id = fields.Many2one(
        comodel_name="retail.purchase.request",
        string="Purchase Request",
        copy=False,
        index=True,
        ondelete="set null",
    )
    retail_approval_ids = fields.One2many(
        comodel_name="retail.purchase.approval",
        inverse_name="order_id",
        string="Approvals",
        copy=False,
    )
    retail_required_group_ids = fields.Many2many(
        comodel_name="res.groups",
        string="Required Approvals",
        compute="_compute_retail_required_group_ids",
    )
    retail_missing_group_ids = fields.Many2many(
        comodel_name="res.groups",
        string="Outstanding Approvals",
        compute="_compute_retail_approval_state",
    )
    retail_approval_state = fields.Selection(
        selection=[
            ("not_required", "No Approval Required"),
            ("pending", "Pending Approval"),
            ("approved", "Fully Approved"),
        ],
        compute="_compute_retail_approval_state",
        string="Approval Status",
    )

    @api.depends("amount_total", "company_id")
    def _compute_retail_required_group_ids(self):
        thresholds = self.env["retail.approval.threshold"].search([])
        for order in self:
            applicable = thresholds.filtered(
                lambda t, order=order: (
                    not t.company_id or t.company_id == order.company_id
                )
            )._matches(order.amount_total)
            order.retail_required_group_ids = applicable.group_id

    @api.depends(
        "retail_required_group_ids",
        "retail_approval_ids.group_id",
    )
    def _compute_retail_approval_state(self):
        for order in self:
            required = order.retail_required_group_ids
            approved = order.retail_approval_ids.group_id
            missing = required - approved
            order.retail_missing_group_ids = missing
            if not required:
                order.retail_approval_state = "not_required"
            elif missing:
                order.retail_approval_state = "pending"
            else:
                order.retail_approval_state = "approved"

    def action_retail_approve(self):
        """Record the current user's approval against one outstanding group."""
        for order in self:
            missing = order.retail_missing_group_ids
            if not missing:
                raise UserError(
                    self.env._(
                        "Purchase order %s has no outstanding approvals.", order.name
                    )
                )
            user_groups = self.env.user.groups_id
            eligible = missing & user_groups
            if not eligible:
                raise UserError(
                    self.env._(
                        "You are not authorised to approve purchase order %(order)s. "
                        "Outstanding approvals: %(groups)s.",
                        order=order.name,
                        groups=", ".join(missing.mapped("name")),
                    )
                )
            self.env["retail.purchase.approval"].create(
                {
                    "order_id": order.id,
                    "group_id": eligible[0].id,
                    "user_id": self.env.user.id,
                    "amount_approved": order.amount_total,
                }
            )
            order.message_post(
                body=self.env._(
                    "Approved as %(group)s by %(user)s.",
                    group=eligible[0].name,
                    user=self.env.user.name,
                )
            )
        return True

    def button_confirm(self):
        for order in self:
            if order.retail_approval_state == "pending":
                raise UserError(
                    self.env._(
                        "Purchase order %(order)s cannot be confirmed. "
                        "Outstanding approvals: %(groups)s.",
                        order=order.name,
                        groups=", ".join(
                            order.retail_missing_group_ids.mapped("name")
                        ),
                    )
                )
        return super().button_confirm()
