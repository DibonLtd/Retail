from odoo import fields
from odoo.tests.common import TransactionCase


class PosReportCase(TransactionCase):
    """Builds real POS orders so the report aggregates genuine data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = "Africa/Nairobi"

        cls.unga = cls._make_product(
            "Bidii Unga Maize Flour 2kg",
            120.0,
            "6001253001001",
            "retail_base.categ_flour_grains",
        )
        cls.milk = cls._make_product(
            "Brookside Full Cream Milk 500ml",
            65.0,
            "6009175982050",
            "retail_base.categ_fresh_dairy",
        )

        cls.config = cls.env["pos.config"].create({"name": "Westgate Till 3"})

        cls.method_cash = cls.env["pos.payment.method"].search(
            [("is_cash_count", "=", True)], limit=1
        )
        if not cls.method_cash:
            cls.method_cash = cls.env["pos.payment.method"].create(
                {
                    "name": "Cash",
                    "journal_id": cls._cash_journal().id,
                }
            )
        cls.method_mpesa = cls.env["pos.payment.method"].create(
            {"name": "Lipa na M-PESA", "retail_payment_bucket": "mpesa"}
        )
        cls.method_card = cls.env["pos.payment.method"].create({"name": "Equity Card"})

        cls.config.payment_method_ids = [
            (6, 0, [cls.method_cash.id, cls.method_mpesa.id, cls.method_card.id])
        ]

    @classmethod
    def _cash_journal(cls):
        return cls.env["account.journal"].search(
            [("type", "=", "cash"), ("company_id", "=", cls.env.company.id)], limit=1
        )

    @classmethod
    def _make_product(cls, name, price, barcode, categ_xmlid):
        return cls.env["product.product"].create(
            {
                "name": name,
                "type": "consu",
                "is_storable": True,
                "available_in_pos": True,
                "list_price": price,
                "barcode": barcode,
                "categ_id": cls.env.ref(categ_xmlid).id,
                "taxes_id": [(5, 0, 0)],
            }
        )

    def _open_session(self):
        session = self.env["pos.session"].create({"config_id": self.config.id})
        session.action_pos_session_open()
        return session

    def _make_order(self, session, lines, payments, order_date=None):
        """Create a paid POS order.

        ``lines`` is a list of (product, qty). ``payments`` is a list of
        (payment_method, amount).
        """
        total = sum(product.list_price * qty for product, qty in lines)
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "company_id": self.env.company.id,
                "amount_tax": 0.0,
                "amount_total": total,
                "amount_paid": total,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "qty": qty,
                            "price_unit": product.list_price,
                            "price_subtotal": product.list_price * qty,
                            "price_subtotal_incl": product.list_price * qty,
                            "tax_ids": [(5, 0, 0)],
                        },
                    )
                    for product, qty in lines
                ],
            }
        )
        for method, amount in payments:
            self.env["pos.payment"].create(
                {
                    "pos_order_id": order.id,
                    "payment_method_id": method.id,
                    "amount": amount,
                }
            )
        order.write({"state": "done"})
        if order_date:
            # date_order is readonly, so it is set through SQL to place the
            # order on a specific trading day.
            self.env.cr.execute(
                "UPDATE pos_order SET date_order = %s WHERE id = %s",
                (order_date, order.id),
            )
            order.invalidate_recordset(["date_order"])
        return order

    def _new_report(self, date_from, date_to, configs=None):
        return self.env["pos.sales.report"].create(
            {
                "date_from": date_from,
                "date_to": date_to,
                "config_ids": [(6, 0, (configs or self.config).ids)],
            }
        )
