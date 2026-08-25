from odoo.tests import tagged

from .common import PurchaseRequestCase


@tagged("post_install", "-at_install")
class TestApprovalThresholds(PurchaseRequestCase):
    """Approval requirements are data, not hardcoded constants."""

    def test_seeded_thresholds_exist(self):
        thresholds = self.env["retail.approval.threshold"].search([])
        self.assertTrue(thresholds, "No approval thresholds were seeded")

    def test_low_value_order_requires_procurement_only(self):
        order = self._make_order(250000.0)
        self.assertEqual(
            order.retail_required_group_ids, self.group_procurement
        )

    def test_order_below_one_million_requires_procurement_only(self):
        """US-PRQ-03 acceptance criteria: procurement approves below KES 1M."""
        order = self._make_order(850000.0)
        self.assertEqual(
            order.retail_required_group_ids, self.group_procurement
        )

    def test_order_above_one_million_also_requires_cfo(self):
        """US-PRQ-03 acceptance criteria: the CFO is required above KES 1M."""
        order = self._make_order(1500000.0)
        self.assertIn(self.group_procurement, order.retail_required_group_ids)
        self.assertIn(self.group_cfo, order.retail_required_group_ids)

    def test_threshold_is_configurable_without_code_change(self):
        """Adding a band changes the requirement, proving it is data-driven."""
        self.env["retail.approval.threshold"].create(
            {
                "name": "Finance above KES 500,000",
                "amount_from": 500000.0,
                "group_id": self.group_finance.id,
                "sequence": 15,
            }
        )
        order = self._make_order(600000.0)
        order.invalidate_recordset(["retail_required_group_ids"])
        self.assertIn(self.group_finance, order.retail_required_group_ids)

    def test_thresholds_are_ordered_by_sequence(self):
        thresholds = self.env["retail.approval.threshold"].search([])
        sequences = thresholds.mapped("sequence")
        self.assertEqual(sequences, sorted(sequences))
