from odoo import fields, models


class FiscalLog(models.Model):
    _name = "fiscal.log"
    _description = "Fiscal Transmission Log"
    _order = "id desc"

    printer_id = fields.Many2one("fiscal.printer", string="Printer", readonly=True)
    endpoint = fields.Char(readonly=True, help="Device address at the time of sending.")
    payload = fields.Text(required=True, readonly=True)
    response = fields.Text(readonly=True)
    error_response = fields.Text(readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one("res.users", string="Cashier", readonly=True)
    pos_order_id = fields.Many2one("pos.order", readonly=True, index=True)
    session_id = fields.Many2one(related="pos_order_id.session_id", store=True)
    config_id = fields.Many2one(related="session_id.config_id", store=True)
    fiscal_receipt_no = fields.Char(readonly=True)
    cu_serial_number = fields.Char("CU Serial (CUSN)", readonly=True)
    cu_invoice_number = fields.Char("CU Invoice (CUIN)", readonly=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )

    def _compute_display_name(self):
        for log in self:
            log.display_name = "%s - %s" % (
                log.pos_order_id.name or log.endpoint or "",
                dict(self._fields["state"].selection).get(log.state, log.state),
            )
