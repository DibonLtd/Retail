from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionRejection(RequisitionCase):
    """TC-STK-03: rejection with a reason, then resubmission."""

    def setUp(self):
        super().setUp()
        self.requisition = self._new_requisition(lines=[(self.unga, 300.0)])

    def _reject(self, reason):
        self.requisition.action_submit()
        wizard = (
            self.env["retail.requisition.reject.wizard"]
            .with_context(active_id=self.requisition.id)
            .create({"reason": reason})
        )
        wizard.action_confirm_rejection()

    def test_tc_stk_03_rejection_stamps_reason_and_rejector(self):
        reason = "Exceeds monthly allocation for Westgate. Reduce to 150 bags."
        self._reject(reason)
        self.assertEqual(self.requisition.state, "rejected")
        self.assertEqual(self.requisition.rejection_reason, reason)
        self.assertEqual(self.requisition.rejected_by_id, self.env.user)

    def test_tc_stk_03_reset_to_draft_clears_rejection(self):
        self._reject("Exceeds monthly allocation.")
        self.requisition.action_reset_to_draft()
        self.assertEqual(self.requisition.state, "draft")
        self.assertFalse(self.requisition.rejection_reason)
        self.assertFalse(self.requisition.rejected_by_id)

    def test_tc_stk_03_resubmission_after_revision(self):
        self._reject("Reduce to 150 bags.")
        self.requisition.action_reset_to_draft()
        self.requisition.line_ids.qty_requested = 150.0
        self.requisition.action_submit()
        self.assertEqual(self.requisition.state, "submitted")
        self.assertEqual(self.requisition.line_ids.qty_requested, 150.0)

    def test_reject_action_opens_wizard(self):
        self.requisition.action_submit()
        action = self.requisition.action_reject()
        self.assertEqual(action["res_model"], "retail.requisition.reject.wizard")
        self.assertEqual(action["context"]["active_id"], self.requisition.id)
