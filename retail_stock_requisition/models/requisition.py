from odoo import api, fields, models
from odoo.exceptions import UserError

REQUISITION_STATES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("sc_validated", "SC Validated"),
    ("finance_approved", "Finance Approved"),
    ("done", "Done"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
]

ROLE_GROUPS = {
    "supply_chain": "retail_base.group_supply_chain_officer",
    "finance": "retail_base.group_finance_officer",
}


class RetailStockRequisition(models.Model):
    _name = "retail.stock.requisition"
    _description = "Retail Stock Requisition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    state = fields.Selection(
        selection=REQUISITION_STATES,
        string="Status",
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
    source_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Source Location",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    dest_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Destination Branch",
        required=True,
        tracking=True,
    )
    dest_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Destination Location",
        compute="_compute_dest_location_id",
        store=True,
        readonly=False,
    )
    date_required = fields.Date(string="Required By")
    line_ids = fields.One2many(
        comodel_name="retail.stock.requisition.line",
        inverse_name="requisition_id",
        string="Products",
        copy=True,
    )
    picking_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="requisition_id",
        string="Transfers",
        readonly=True,
    )
    picking_count = fields.Integer(compute="_compute_picking_count")
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    rejection_reason = fields.Text(readonly=True, copy=False)
    rejected_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    sc_validated_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    sc_validated_date = fields.Datetime(readonly=True, copy=False)
    finance_approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    finance_approved_date = fields.Datetime(readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("dest_warehouse_id")
    def _compute_dest_location_id(self):
        for requisition in self:
            requisition.dest_location_id = requisition.dest_warehouse_id.lot_stock_id

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for requisition in self:
            requisition.picking_count = len(requisition.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("retail.stock.requisition")
                    or "New"
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _notify_role(self, role, body):
        """Post a chatter message notifying the users holding ``role``."""
        self.ensure_one()
        if role == "requestor":
            partners = self.requestor_id.partner_id
        else:
            group = self.env.ref(ROLE_GROUPS[role], raise_if_not_found=False)
            partners = group.users.partner_id if group else self.env["res.partner"]
        if not partners:
            return False
        return self.message_post(
            body=body,
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_comment",
        )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _check_destination_authorised(self):
        """Raise if the requestor may not transact against the destination."""
        for requisition in self:
            user = requisition.requestor_id
            if not user._is_warehouse_allowed(requisition.dest_warehouse_id):
                raise UserError(
                    self.env._(
                        "You are not authorised to submit requisitions to '%s'. "
                        "Please select one of your assigned destination branches.",
                        requisition.dest_warehouse_id.name,
                    )
                )

    def action_submit(self):
        for requisition in self:
            if requisition.state != "draft":
                raise UserError(
                    self.env._("Only draft requisitions can be submitted.")
                )
            if not requisition.line_ids:
                raise UserError(
                    self.env._("Add at least one product before submitting.")
                )
            requisition._check_destination_authorised()
        self.write({"state": "submitted"})
        for requisition in self:
            requisition._notify_role(
                "supply_chain",
                self.env._(
                    "Requisition %(name)s for %(branch)s awaits supply chain validation.",
                    name=requisition.name,
                    branch=requisition.dest_warehouse_id.name,
                ),
            )
        return True

    def action_sc_validate(self):
        for requisition in self:
            if requisition.state != "submitted":
                raise UserError(
                    self.env._("Only submitted requisitions can be validated.")
                )
        self.write(
            {
                "state": "sc_validated",
                "sc_validated_by_id": self.env.user.id,
                "sc_validated_date": fields.Datetime.now(),
            }
        )
        for requisition in self:
            requisition._notify_role(
                "finance",
                self.env._(
                    "Requisition %(name)s has been validated and awaits finance approval.",
                    name=requisition.name,
                ),
            )
        return True

    def action_finance_approve(self):
        for requisition in self:
            if requisition.state != "sc_validated":
                raise UserError(
                    self.env._(
                        "Only supply-chain-validated requisitions can be approved."
                    )
                )
            requisition._create_internal_picking()
        self.write(
            {
                "state": "finance_approved",
                "finance_approved_by_id": self.env.user.id,
                "finance_approved_date": fields.Datetime.now(),
            }
        )
        for requisition in self:
            requisition._notify_role(
                "requestor",
                self.env._(
                    "Transfer in progress for %(branch)s against requisition %(name)s.",
                    branch=requisition.dest_warehouse_id.name,
                    name=requisition.name,
                ),
            )
        return True

    def action_reject(self):
        self.ensure_one()
        if self.state not in ("submitted", "sc_validated"):
            raise UserError(
                self.env._("Only submitted or validated requisitions can be rejected.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reject Requisition"),
            "res_model": "retail.requisition.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def _apply_rejection(self, reason):
        self.ensure_one()
        self.write(
            {
                "state": "rejected",
                "rejection_reason": reason,
                "rejected_by_id": self.env.user.id,
            }
        )
        self._notify_role(
            "requestor",
            self.env._(
                "Requisition %(name)s was rejected: %(reason)s",
                name=self.name,
                reason=reason,
            ),
        )
        return True

    def action_reset_to_draft(self):
        for requisition in self:
            if requisition.state not in ("rejected", "cancelled"):
                raise UserError(
                    self.env._(
                        "Only rejected or cancelled requisitions can be reset to draft."
                    )
                )
        self.write(
            {
                "state": "draft",
                "rejection_reason": False,
                "rejected_by_id": False,
            }
        )
        return True

    def action_cancel(self):
        for requisition in self:
            if requisition.state not in ("draft", "submitted"):
                raise UserError(
                    self.env._(
                        "Only draft or submitted requisitions can be cancelled. "
                        "Requisition %(name)s is in state %(state)s.",
                        name=requisition.name,
                        state=requisition.state,
                    )
                )
        self.write({"state": "cancelled"})
        return True

    # ------------------------------------------------------------------
    # Transfers
    # ------------------------------------------------------------------

    def _get_internal_picking_type(self):
        """Return the internal picking type serving the source warehouse."""
        self.ensure_one()
        warehouse = self.source_location_id.warehouse_id
        picking_type = warehouse.int_type_id
        if not picking_type:
            picking_type = self.env["stock.picking.type"].search(
                [("code", "=", "internal"), ("company_id", "=", self.company_id.id)],
                limit=1,
            )
        if not picking_type:
            raise UserError(
                self.env._("No internal transfer operation type is configured.")
            )
        return picking_type

    def _create_internal_picking(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: line.qty_approved > 0)
        if not lines:
            raise UserError(
                self.env._("Approve at least one product quantity before approving.")
            )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self._get_internal_picking_type().id,
                "location_id": self.source_location_id.id,
                "location_dest_id": self.dest_location_id.id,
                "origin": self.name,
                "requisition_id": self.id,
                "scheduled_date": self.date_required or fields.Datetime.now(),
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": line.product_id.display_name,
                            "product_id": line.product_id.id,
                            "product_uom_qty": line.qty_approved,
                            "product_uom": line.product_uom_id.id,
                            "location_id": self.source_location_id.id,
                            "location_dest_id": self.dest_location_id.id,
                        },
                    )
                    for line in lines
                ],
            }
        )
        picking.action_confirm()
        return picking

    def _action_set_done(self):
        """Close the requisition once every linked transfer is complete."""
        for requisition in self:
            if requisition.state != "finance_approved":
                continue
            pickings = requisition.picking_ids
            if pickings and all(
                picking.state in ("done", "cancel") for picking in pickings
            ):
                requisition.state = "done"
        return True

    def action_view_pickings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Transfers"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("requisition_id", "=", self.id)],
        }
