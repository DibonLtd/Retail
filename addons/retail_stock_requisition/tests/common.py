from odoo.tests.common import TransactionCase


class RequisitionCase(TransactionCase):
    """Shared fixtures for the Tano stock requisition suite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.city_mall = cls.env.ref("retail_base.warehouse_city_mall")

        cls.unga = cls._make_product("Bidii Unga Maize Flour 2kg")
        cls.milk = cls._make_product("Brookside Full Cream Milk 500ml")
        cls.royco = cls._make_product("Royco Mchuzi Mix 200g")
        cls.dettol = cls._make_product("Dettol Antiseptic Liquid 200ml")

    @classmethod
    def _make_product(cls, name):
        return cls.env["product.product"].create(
            {"name": name, "type": "consu", "is_storable": True}
        )

    @classmethod
    def _stock_up(cls, product, qty, location=None):
        """Put ``qty`` of ``product`` into the source location."""
        location = location or cls.central.lot_stock_id
        cls.env["stock.quant"]._update_available_quantity(product, location, qty)

    def _new_requisition(self, lines=None, dest=None, user=None):
        """Create a draft requisition. ``lines`` is a list of (product, qty)."""
        lines = lines or [(self.unga, 100.0)]
        model = self.env["retail.stock.requisition"]
        if user:
            model = model.with_user(user)
        return model.create(
            {
                "source_location_id": self.central.lot_stock_id.id,
                "dest_warehouse_id": (dest or self.westgate).id,
                "line_ids": [
                    (0, 0, {"product_id": product.id, "qty_requested": qty})
                    for product, qty in lines
                ],
            }
        )
