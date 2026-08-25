from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionAuthorisation(RequisitionCase):
    """TC-STK-02: submission to an unassigned branch is blocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agnes = cls.env["res.users"].create(
            {
                "name": "Agnes Wanjiku",
                "login": "agnes.auth.test",
                "groups_id": [
                    (4, cls.env.ref("point_of_sale.group_pos_manager").id),
                    (4, cls.env.ref("stock.group_stock_user").id),
                ],
                "retail_warehouse_ids": [(6, 0, [cls.westgate.id])],
            }
        )

    def test_tc_stk_02_unauthorised_station_blocked(self):
        requisition = self._new_requisition(dest=self.city_mall, user=self.agnes)
        with self.assertRaises(UserError) as ctx:
            requisition.with_user(self.agnes).action_submit()
        self.assertIn("City Mall Branch", str(ctx.exception))
        self.assertEqual(requisition.state, "draft")

    def test_assigned_station_submits_successfully(self):
        requisition = self._new_requisition(dest=self.westgate, user=self.agnes)
        requisition.with_user(self.agnes).action_submit()
        self.assertEqual(requisition.state, "submitted")

    def test_submitting_without_lines_is_blocked(self):
        requisition = self.env["retail.stock.requisition"].create(
            {
                "source_location_id": self.central.lot_stock_id.id,
                "dest_warehouse_id": self.westgate.id,
            }
        )
        with self.assertRaises(UserError):
            requisition.action_submit()
