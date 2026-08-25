from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestUserWarehouses(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wh_westgate = cls.env["stock.warehouse"].create(
            {"name": "Westgate Test WH", "code": "WGTT"}
        )
        cls.wh_citymall = cls.env["stock.warehouse"].create(
            {"name": "City Mall Test WH", "code": "CTMT"}
        )
        cls.user = cls.env["res.users"].create(
            {
                "name": "Agnes Wanjiku",
                "login": "agnes.wh.test",
                "retail_warehouse_ids": [(6, 0, [cls.wh_westgate.id])],
            }
        )

    def test_assigned_warehouse_is_allowed(self):
        self.assertTrue(self.user._is_warehouse_allowed(self.wh_westgate))

    def test_unassigned_warehouse_is_not_allowed(self):
        self.assertFalse(self.user._is_warehouse_allowed(self.wh_citymall))

    def test_user_with_no_assignment_is_allowed_everywhere(self):
        """An empty assignment means unrestricted, so head office is not locked out."""
        head_office = self.env["res.users"].create(
            {"name": "Joseph Mwangi", "login": "joseph.wh.test"}
        )
        self.assertTrue(head_office._is_warehouse_allowed(self.wh_citymall))
