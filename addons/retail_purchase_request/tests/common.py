from odoo.tests.common import TransactionCase


class PurchaseRequestCase(TransactionCase):
    """Shared fixtures for the purchase request and approval suite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_procurement = cls.env.ref("retail_base.group_procurement_manager")
        cls.group_finance = cls.env.ref("retail_base.group_finance_officer")
        cls.group_cfo = cls.env.ref("retail_base.group_purchase_cfo")
        cls.group_purchase_user = cls.env.ref("purchase.group_purchase_user")

        cls.vendor = cls.env["res.partner"].create({"name": "Bidco Africa Ltd"})
        cls.diapers = cls.env["product.product"].create(
            {
                "name": "Pampers Size 4 Diapers 40-pack",
                "type": "consu",
                "is_storable": True,
                "standard_price": 1200.0,
                "list_price": 1500.0,
                # Explicit, so the fixture does not inherit whatever sales
                # taxes the company's localisation happens to default to.
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
            }
        )

        cls.lydiah = cls._make_user(
            "Lydiah Muthoni", "lydiah.test", [cls.group_procurement, cls.group_purchase_user]
        )
        cls.susan = cls._make_user(
            "Susan Achieng", "susan.test", [cls.group_cfo, cls.group_purchase_user]
        )
        cls.margaret = cls._make_user(
            "Margaret Otieno", "margaret.pr.test", [cls.group_finance, cls.group_purchase_user]
        )
        cls.david = cls._make_user(
            "David Kamau", "david.pr.test", [cls.group_purchase_user]
        )

    @classmethod
    def _make_user(cls, name, login, groups):
        return cls.env["res.users"].create(
            {
                "name": name,
                "login": login,
                "email": "%s@tano.test" % login,
                "groups_id": [(4, group.id) for group in groups],
            }
        )

    def _make_order(self, amount):
        """Create a draft purchase order whose total equals ``amount``."""
        return self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.diapers.id,
                            "product_qty": 1.0,
                            "price_unit": amount,
                            "taxes_id": [(5, 0, 0)],
                        },
                    )
                ],
            }
        )

    def _make_request(self, qty=200.0, user=None):
        model = self.env["retail.purchase.request"]
        if user:
            model = model.with_user(user)
        return model.create(
            {
                "preferred_vendor_id": self.vendor.id,
                "justification": "Shelf stock exhausted at Westgate.",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.diapers.id,
                            "qty_requested": qty,
                            "estimated_price": 1200.0,
                        },
                    )
                ],
            }
        )
