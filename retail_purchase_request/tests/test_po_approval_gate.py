from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PurchaseRequestCase


@tagged("post_install", "-at_install")
class TestPoApprovalGate(PurchaseRequestCase):
    """US-PRQ-03: a purchase order cannot be confirmed without its approvals."""

    def test_confirm_blocked_without_any_approval(self):
        order = self._make_order(850000.0)
        with self.assertRaises(UserError):
            order.button_confirm()
        self.assertEqual(order.state, "draft")

    def test_confirm_allowed_after_procurement_approval(self):
        order = self._make_order(850000.0)
        order.with_user(self.lydiah).action_retail_approve()
        order.button_confirm()
        self.assertEqual(order.state, "purchase")

    def test_high_value_needs_two_approvals(self):
        order = self._make_order(1500000.0)
        order.with_user(self.lydiah).action_retail_approve()
        with self.assertRaises(UserError):
            order.button_confirm()
        order.with_user(self.susan).action_retail_approve()
        order.button_confirm()
        self.assertEqual(order.state, "purchase")

    def test_user_without_required_group_cannot_approve(self):
        order = self._make_order(850000.0)
        with self.assertRaises(UserError):
            order.with_user(self.david).action_retail_approve()

    def test_approval_is_recorded_with_approver_and_group(self):
        order = self._make_order(850000.0)
        order.with_user(self.lydiah).action_retail_approve()
        approval = order.retail_approval_ids
        self.assertEqual(len(approval), 1)
        self.assertEqual(approval.user_id, self.lydiah)
        self.assertEqual(approval.group_id, self.group_procurement)
        self.assertTrue(approval.approval_date)

    def test_same_user_cannot_approve_twice_for_one_group(self):
        order = self._make_order(850000.0)
        order.with_user(self.lydiah).action_retail_approve()
        with self.assertRaises(UserError):
            order.with_user(self.lydiah).action_retail_approve()

    def test_approval_state_reflects_progress(self):
        order = self._make_order(1500000.0)
        self.assertEqual(order.retail_approval_state, "pending")
        order.with_user(self.lydiah).action_retail_approve()
        self.assertEqual(order.retail_approval_state, "pending")
        order.with_user(self.susan).action_retail_approve()
        self.assertEqual(order.retail_approval_state, "approved")

    def test_editing_amount_upward_reopens_approval(self):
        """Raising the total past a threshold must not keep a stale approval."""
        order = self._make_order(850000.0)
        order.with_user(self.lydiah).action_retail_approve()
        self.assertEqual(order.retail_approval_state, "approved")
        order.order_line.price_unit = 1500000.0
        self.assertEqual(order.retail_approval_state, "pending")
        with self.assertRaises(UserError):
            order.button_confirm()
