from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionFlow(RequisitionCase):
    """TC-STK-01: full approval flow, Westgate branch replenishment."""

    def setUp(self):
        super().setUp()
        self.requisition = self._new_requisition(
            lines=[(self.unga, 100.0), (self.milk, 200.0)]
        )

    def test_tc_stk_01_full_approval_flow(self):
        self.requisition.action_submit()
        self.assertEqual(self.requisition.state, "submitted")

        # Supply chain trims Brookside from 200 to 150 -- only 150 available.
        milk_line = self.requisition.line_ids.filtered(
            lambda line: line.product_id == self.milk
        )
        milk_line.qty_approved = 150.0
        self.requisition.action_sc_validate()
        self.assertEqual(self.requisition.state, "sc_validated")
        self.assertEqual(self.requisition.sc_validated_by_id, self.env.user)
        self.assertTrue(self.requisition.sc_validated_date)

        self.requisition.action_finance_approve()
        self.assertEqual(self.requisition.state, "finance_approved")
        self.assertEqual(self.requisition.finance_approved_by_id, self.env.user)
        self.assertEqual(len(self.requisition.picking_ids), 1)

        picking = self.requisition.picking_ids
        self.assertEqual(picking.location_id, self.central.lot_stock_id)
        self.assertEqual(picking.location_dest_id, self.westgate.lot_stock_id)
        self.assertEqual(len(picking.move_ids), 2)
        self.assertEqual(picking.origin, self.requisition.name)

        moved_milk = picking.move_ids.filtered(
            lambda move: move.product_id == self.milk
        )
        self.assertEqual(
            moved_milk.product_uom_qty,
            150.0,
            "The transfer must carry the approved quantity, not the requested one.",
        )

    def test_approval_uses_approved_not_requested_quantity(self):
        self.requisition.action_submit()
        unga_line = self.requisition.line_ids.filtered(
            lambda line: line.product_id == self.unga
        )
        unga_line.qty_approved = 80.0
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        move = self.requisition.picking_ids.move_ids.filtered(
            lambda m: m.product_id == self.unga
        )
        self.assertEqual(move.product_uom_qty, 80.0)

    def test_zero_approved_lines_are_not_transferred(self):
        self.requisition.action_submit()
        self.requisition.line_ids.filtered(
            lambda line: line.product_id == self.milk
        ).qty_approved = 0.0
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        self.assertEqual(len(self.requisition.picking_ids.move_ids), 1)

    def test_states_cannot_be_skipped(self):
        """Finance cannot approve a requisition supply chain has not validated."""
        from odoo.exceptions import UserError

        self.requisition.action_submit()
        with self.assertRaises(UserError):
            self.requisition.action_finance_approve()
