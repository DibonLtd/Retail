from odoo.tests.common import TransactionCase

PRINTER_PATH = "odoo.addons.retail_fiscal_ke.models.fiscal_printer.FiscalPrinter"


class FiscalCase(TransactionCase):
    """A till with a fiscal printer. The device socket is always mocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.printer = cls.env["fiscal.printer"].create(
            {
                "name": "Westgate Till 3 ESD",
                "ip_address": "192.168.0.50",
                "port": 6001,
                "company_id": cls.company.id,
            }
        )
        cls.company.write(
            {
                "retail_fiscal_enabled": True,
                "retail_fiscal_printer_id": cls.printer.id,
            }
        )

        # A mixed Kenyan basket: standard rated, zero rated and exempt.
        cls.tax_standard = cls.env["account.tax"].create(
            {
                "name": "VAT 16%",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "factor_type": "taxable",
                "fiscal_ptu_value": "B",
                "company_id": cls.company.id,
            }
        )
        cls.tax_zero = cls.env["account.tax"].create(
            {
                "name": "VAT Zero Rated",
                "amount": 0.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "factor_type": "zero",
                "fiscal_ptu_value": "C",
                "company_id": cls.company.id,
            }
        )
        cls.tax_exempt = cls.env["account.tax"].create(
            {
                "name": "VAT Exempt",
                "amount": 0.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "factor_type": "exempted",
                "fiscal_ptu_value": "A",
                "company_id": cls.company.id,
            }
        )

        # Royco is standard rated; unga and milk are not.
        cls.royco = cls._make_product("Royco Mchuzi Mix 200g", 45.0, cls.tax_standard)
        cls.unga = cls._make_product(
            "Bidii Unga Maize Flour 2kg", 120.0, cls.tax_zero, hs_code="1102.20.00"
        )
        cls.milk = cls._make_product(
            "Brookside Full Cream Milk 500ml", 65.0, cls.tax_exempt
        )

        cash_journal = cls.env["account.journal"].create(
            {
                "name": "Tano Fiscal Test Cash",
                "type": "cash",
                "code": "TFTC",
                "company_id": cls.company.id,
            }
        )
        cls.method_cash = cls.env["pos.payment.method"].create(
            {
                "name": "Cash (fiscal test)",
                "journal_id": cash_journal.id,
                "company_id": cls.company.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Westgate Till 3",
                "payment_method_ids": [(6, 0, [cls.method_cash.id])],
                "retail_fiscal_printer_id": cls.printer.id,
            }
        )

    @classmethod
    def _make_product(cls, name, price, tax, hs_code=None):
        return cls.env["product.product"].create(
            {
                "name": name,
                "type": "consu",
                "is_storable": True,
                "available_in_pos": True,
                "list_price": price,
                "taxes_id": [(6, 0, [tax.id])],
                "hscode_index": hs_code,
            }
        )

    def _open_session(self):
        session = self.env["pos.session"].create({"config_id": self.config.id})
        session.action_pos_session_open()
        return session

    def _order(self, session, lines):
        """``lines`` is a list of (product, qty)."""
        total = sum(product.list_price * qty for product, qty in lines)
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "company_id": self.company.id,
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
                            "tax_ids": [(6, 0, product.taxes_id.ids)],
                        },
                    )
                    for product, qty in lines
                ],
            }
        )
        order.write({"state": "done"})
        return order
