from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import RetailPosCase


@tagged("post_install", "-at_install")
class TestReturnWindow(RetailPosCase):
    """US-POS-07: returns are only accepted inside the configured window."""

    def setUp(self):
        super().setUp()
        self._stock_up(self.unga, 100.0)
        self.session = self.env["pos.session"].create({"config_id": self.config.id})
        self.session.action_pos_session_open()

    def _order(self, days_ago=0):
        order = self.env["pos.order"].create(
            {
                "session_id": self.session.id,
                "company_id": self.env.company.id,
                "amount_tax": 0.0,
                "amount_total": 240.0,
                "amount_paid": 240.0,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.unga.id,
                            "qty": 2,
                            "price_unit": 120.0,
                            "price_subtotal": 240.0,
                            "price_subtotal_incl": 240.0,
                            "tax_ids": [(5, 0, 0)],
                        },
                    )
                ],
            }
        )
        order.write({"state": "done"})
        if days_ago:
            self.env.flush_all()
            sold_on = fields.Datetime.now() - timedelta(days=days_ago)
            self.env.cr.execute(
                "UPDATE pos_order SET date_order = %s WHERE id = %s",
                (sold_on, order.id),
            )
            order.invalidate_recordset(["date_order"])
        return order

    def test_default_window_is_seven_days(self):
        self.assertEqual(self.config.retail_return_window_days, 7)

    def test_return_inside_window_is_allowed(self):
        order = self._order(days_ago=3)
        refund = order._refund()
        self.assertTrue(refund)
        self.assertEqual(refund.refunded_order_id, order)

    def test_return_on_the_boundary_is_allowed(self):
        order = self._order(days_ago=7)
        self.assertTrue(order._refund())

    def test_return_outside_window_is_refused(self):
        order = self._order(days_ago=10)
        with self.assertRaises(UserError) as ctx:
            order._refund()
        self.assertIn("return window", str(ctx.exception))

    def test_zero_window_means_no_limit(self):
        self.config.retail_return_window_days = 0
        order = self._order(days_ago=400)
        self.assertTrue(
            order._refund(), "A zero window must allow returns indefinitely."
        )

    def test_window_is_read_from_the_selling_till(self):
        self.config.retail_return_window_days = 30
        order = self._order(days_ago=20)
        self.assertTrue(order._refund())
