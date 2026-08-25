from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    requisition_id = fields.Many2one(
        comodel_name="retail.stock.requisition",
        string="Stock Requisition",
        copy=False,
        index=True,
        ondelete="set null",
    )

    def button_validate(self):
        result = super().button_validate()
        # ``_action_set_done`` re-checks that every linked picking actually
        # reached ``done``, so it is safe to call even when ``button_validate``
        # returned a backorder or immediate-transfer wizard action.
        self.filtered("requisition_id").requisition_id._action_set_done()
        return result
