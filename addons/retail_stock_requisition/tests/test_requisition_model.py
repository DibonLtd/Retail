from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionModel(RequisitionCase):

    def test_reference_is_generated(self):
        requisition = self._new_requisition()
        self.assertTrue(requisition.name.startswith("RSR/"))
        self.assertNotEqual(requisition.name, "New")

    def test_starts_in_draft(self):
        self.assertEqual(self._new_requisition().state, "draft")

    def test_requestor_defaults_to_current_user(self):
        self.assertEqual(self._new_requisition().requestor_id, self.env.user)

    def test_approved_qty_defaults_to_requested(self):
        requisition = self._new_requisition()
        self.assertEqual(requisition.line_ids.qty_approved, 100.0)

    def test_destination_location_follows_warehouse(self):
        requisition = self._new_requisition()
        self.assertEqual(
            requisition.dest_location_id, self.westgate.lot_stock_id
        )

    def test_available_quantity_at_source_is_reported(self):
        self._stock_up(self.royco, 250.0)
        requisition = self._new_requisition(lines=[(self.royco, 80.0)])
        self.assertEqual(requisition.line_ids.qty_available_source, 250.0)
