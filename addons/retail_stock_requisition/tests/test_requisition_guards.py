from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionGuards(RequisitionCase):
    """US-STK-06: cancellation is restricted to early states."""

    def test_draft_can_be_cancelled(self):
        requisition = self._new_requisition(lines=[(self.royco, 10.0)])
        requisition.action_cancel()
        self.assertEqual(requisition.state, "cancelled")

    def test_submitted_can_be_cancelled(self):
        requisition = self._new_requisition(lines=[(self.royco, 10.0)])
        requisition.action_submit()
        requisition.action_cancel()
        self.assertEqual(requisition.state, "cancelled")

    def test_finance_approved_cannot_be_cancelled(self):
        requisition = self._new_requisition(lines=[(self.royco, 10.0)])
        requisition.action_submit()
        requisition.action_sc_validate()
        requisition.action_finance_approve()
        with self.assertRaises(UserError):
            requisition.action_cancel()
        self.assertEqual(requisition.state, "finance_approved")

    def test_cancelled_can_be_reset_to_draft(self):
        requisition = self._new_requisition(lines=[(self.royco, 10.0)])
        requisition.action_cancel()
        requisition.action_reset_to_draft()
        self.assertEqual(requisition.state, "draft")

    def test_draft_cannot_be_validated_by_supply_chain(self):
        requisition = self._new_requisition(lines=[(self.royco, 10.0)])
        with self.assertRaises(UserError):
            requisition.action_sc_validate()
