from odoo import fields, models
from odoo.exceptions import UserError


class RetailPurchaseRequestRejectWizard(models.TransientModel):
    _name = "retail.purchase.request.reject.wizard"
    _description = "Reject Purchase Request"

    reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        active_id = self.env.context.get("active_id")
        if not active_id:
            raise UserError(self.env._("No purchase request selected."))
        request = self.env["retail.purchase.request"].browse(active_id)
        request.action_reject_with_reason(self.reason)
        return {"type": "ir.actions.act_window_close"}
