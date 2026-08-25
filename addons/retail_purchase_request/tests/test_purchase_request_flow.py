from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PurchaseRequestCase


@tagged("post_install", "-at_install")
class TestPurchaseRequestFlow(PurchaseRequestCase):
    """US-PRQ-01 and US-PRQ-02: raise a request, approve it, create the RFQ."""

    def test_us_prq_01_reference_is_generated(self):
        request = self._make_request()
        self.assertTrue(request.name.startswith("PR/"))
        self.assertEqual(request.state, "draft")

    def test_us_prq_01_submit_notifies_procurement(self):
        request = self._make_request()
        request.action_submit()
        self.assertEqual(request.state, "submitted")
        partners = request.message_ids.mapped("partner_ids")
        self.assertIn(self.lydiah.partner_id, partners)

    def test_estimated_total_is_computed(self):
        request = self._make_request(qty=200.0)
        self.assertEqual(request.amount_estimated, 200.0 * 1200.0)

    def test_us_prq_02_approval_then_rfq_creation(self):
        request = self._make_request()
        request.action_submit()
        request.with_user(self.lydiah).action_approve()
        self.assertEqual(request.state, "approved")

        request.with_user(self.lydiah).action_create_rfq()
        self.assertEqual(request.state, "rfq_created")
        self.assertEqual(len(request.purchase_order_ids), 1)

        order = request.purchase_order_ids
        self.assertEqual(order.partner_id, self.vendor)
        self.assertEqual(order.state, "draft")
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_qty, 200.0)
        self.assertEqual(order.order_line.product_id, self.diapers)

    def test_rfq_requires_approval_first(self):
        request = self._make_request()
        request.action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.lydiah).action_create_rfq()

    def test_non_procurement_user_cannot_approve(self):
        request = self._make_request()
        request.action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.david).action_approve()

    def test_rejection_records_reason(self):
        request = self._make_request()
        request.action_submit()
        request.with_user(self.lydiah).action_reject_with_reason("Not budgeted.")
        self.assertEqual(request.state, "rejected")
        self.assertEqual(request.rejection_reason, "Not budgeted.")

    def test_created_order_links_back_to_request(self):
        request = self._make_request()
        request.action_submit()
        request.with_user(self.lydiah).action_approve()
        request.with_user(self.lydiah).action_create_rfq()
        self.assertEqual(request.purchase_order_ids.retail_request_id, request)

    def test_submitting_without_lines_is_blocked(self):
        request = self.env["retail.purchase.request"].create(
            {"preferred_vendor_id": self.vendor.id}
        )
        with self.assertRaises(UserError):
            request.action_submit()
