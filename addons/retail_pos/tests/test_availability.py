from odoo.tests import tagged

from .common import RetailPosCase


@tagged("post_install", "-at_install")
class TestAvailability(RetailPosCase):
    """TC-POS-03: an out-of-stock item must not reach the cart."""

    def test_tc_pos_03_zero_stock_item_is_unavailable(self):
        self.assertFalse(
            self.env["product.product"].is_retail_available(
                self.diapers.id, self.config.id
            ),
            "A storable product with no stock must be refused.",
        )

    def test_tc_pos_03_substitute_with_stock_is_available(self):
        """Agnes offers an alternative that does have stock."""
        self._stock_up(self.unga, 12.0)
        self.assertTrue(
            self.env["product.product"].is_retail_available(
                self.unga.id, self.config.id
            )
        )

    def test_negative_stock_is_unavailable(self):
        self._stock_up(self.diapers, -3.0)
        self.assertFalse(
            self.env["product.product"].is_retail_available(
                self.diapers.id, self.config.id
            )
        )

    def test_service_products_are_always_available(self):
        """A service has no stock figure, so there is nothing to block on."""
        self.assertTrue(
            self.env["product.product"].is_retail_available(
                self.bag.id, self.config.id
            )
        )

    def test_guard_can_be_switched_off_per_till(self):
        self.config.retail_block_zero_qty = False
        self.assertTrue(
            self.env["product.product"].is_retail_available(
                self.diapers.id, self.config.id
            ),
            "With the guard off, the till must sell regardless of stock.",
        )

    def test_availability_is_measured_at_the_till_warehouse(self):
        """Stock at another branch must not make this till think it has some."""
        other = self.env.ref("retail_base.warehouse_city_mall")
        self.env["stock.quant"]._update_available_quantity(
            self.diapers, other.lot_stock_id, 50.0
        )
        self.assertFalse(
            self.env["product.product"].is_retail_available(
                self.diapers.id, self.config.id
            ),
            "City Mall stock is not Westgate stock.",
        )

    def test_bulk_availability_returns_one_entry_per_product(self):
        self._stock_up(self.unga, 8.0)
        result = self.env["product.product"].get_retail_availability(
            [self.unga.id, self.diapers.id], self.config.id
        )
        self.assertEqual(result[self.unga.id], 8.0)
        self.assertEqual(result[self.diapers.id], 0.0)

    def test_unknown_product_is_not_available(self):
        self.assertFalse(
            self.env["product.product"].is_retail_available(0, self.config.id)
        )
