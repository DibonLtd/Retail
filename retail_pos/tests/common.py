from odoo.tests.common import TransactionCase


class RetailPosCase(TransactionCase):
    """Fixtures for till behaviour: a config with its own warehouse and cash."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env.ref("retail_base.warehouse_westgate")

        cls.picking_type_out = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("warehouse_id", "=", cls.warehouse.id)],
            limit=1,
        )

        # Odoo 18 refuses to share a cash payment method between POS configs,
        # so this fixture owns its own journal and method.
        cash_journal = cls.env["account.journal"].create(
            {
                "name": "Tano POS Test Cash",
                "type": "cash",
                "code": "TPTC",
                "company_id": cls.env.company.id,
            }
        )
        cls.method_cash = cls.env["pos.payment.method"].create(
            {
                "name": "Cash (pos test)",
                "journal_id": cash_journal.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Westgate Till 3",
                "picking_type_id": cls.picking_type_out.id,
                "payment_method_ids": [(6, 0, [cls.method_cash.id])],
            }
        )

        cls.unga = cls._make_product("Bidii Unga Maize Flour 2kg", 120.0)
        cls.diapers = cls._make_product("Pampers Size 3 Diapers 40-pack", 1450.0)
        cls.bag = cls._make_service("Carrier Bag")

    @classmethod
    def _make_product(cls, name, price):
        return cls.env["product.product"].create(
            {
                "name": name,
                "type": "consu",
                "is_storable": True,
                "available_in_pos": True,
                "list_price": price,
                "taxes_id": [(5, 0, 0)],
            }
        )

    @classmethod
    def _make_service(cls, name):
        return cls.env["product.product"].create(
            {
                "name": name,
                "type": "service",
                "available_in_pos": True,
                "list_price": 5.0,
                "taxes_id": [(5, 0, 0)],
            }
        )

    @classmethod
    def _stock_up(cls, product, qty):
        cls.env["stock.quant"]._update_available_quantity(
            product, cls.warehouse.lot_stock_id, qty
        )
