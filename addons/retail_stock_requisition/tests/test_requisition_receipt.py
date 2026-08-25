from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionReceipt(RequisitionCase):
    """US-STK-04: validating the transfer closes the requisition."""

    def setUp(self):
        super().setUp()
        self._stock_up(self.dettol, 500.0)
        self.requisition = self._new_requisition(lines=[(self.dettol, 40.0)])
        self.requisition.action_submit()
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        self.picking = self.requisition.picking_ids

    def _receive_everything(self):
        for move in self.picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self.picking.button_validate()

    def test_validating_picking_sets_requisition_done(self):
        self._receive_everything()
        self.assertEqual(self.picking.state, "done")
        self.assertEqual(self.requisition.state, "done")

    def test_branch_stock_increases_by_received_quantity(self):
        self._receive_everything()
        branch_qty = self.dettol.with_context(
            location=self.westgate.lot_stock_id.id
        ).qty_available
        self.assertEqual(branch_qty, 40.0)
        self.assertEqual(self.requisition.line_ids.qty_received, 40.0)

    def test_requisition_stays_open_until_picking_validated(self):
        self.assertEqual(self.requisition.state, "finance_approved")
        self.assertNotEqual(self.picking.state, "done")
