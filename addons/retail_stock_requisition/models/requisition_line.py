from odoo import api, fields, models


class RetailStockRequisitionLine(models.Model):
    _name = "retail.stock.requisition.line"
    _description = "Retail Stock Requisition Line"

    requisition_id = fields.Many2one(
        comodel_name="retail.stock.requisition",
        string="Requisition",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
    )
    qty_requested = fields.Float(
        string="Requested Qty",
        default=1.0,
        digits="Product Unit of Measure",
    )
    qty_approved = fields.Float(
        string="Approved Qty",
        compute="_compute_qty_approved",
        store=True,
        readonly=False,
        digits="Product Unit of Measure",
        help="Quantity endorsed by the supply chain officer.",
    )
    qty_received = fields.Float(
        string="Received Qty",
        compute="_compute_qty_received",
        digits="Product Unit of Measure",
    )
    qty_available_source = fields.Float(
        string="Available at Source",
        compute="_compute_qty_available_source",
        digits="Product Unit of Measure",
        help="On-hand quantity at the requisition source location.",
    )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    @api.depends("qty_requested")
    def _compute_qty_approved(self):
        for line in self:
            line.qty_approved = line.qty_requested

    @api.depends("requisition_id.picking_ids.state", "product_id")
    def _compute_qty_received(self):
        for line in self:
            moves = line.requisition_id.picking_ids.move_ids.filtered(
                lambda m, line=line: m.product_id == line.product_id
                and m.state == "done"
            )
            line.qty_received = sum(moves.mapped("quantity"))

    @api.depends("product_id", "requisition_id.source_location_id")
    def _compute_qty_available_source(self):
        for line in self:
            location = line.requisition_id.source_location_id
            if not line.product_id or not location:
                line.qty_available_source = 0.0
                continue
            line.qty_available_source = line.product_id.with_context(
                location=location.id
            ).qty_available
