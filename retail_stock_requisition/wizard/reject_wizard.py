from odoo import fields, models
from odoo.exceptions import UserError


class RetailRequisitionRejectWizard(models.TransientModel):
    _name = "retail.requisition.reject.wizard"
    _description = "Reject Stock Requisition"

    reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        active_id = self.env.context.get("active_id")
        if not active_id:
            raise UserError(self.env._("No requisition selected for rejection."))
        requisition = self.env["retail.stock.requisition"].browse(active_id)
        requisition._apply_rejection(self.reason)
        return {"type": "ir.actions.act_window_close"}
