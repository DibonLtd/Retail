from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import FiscalCase


@tagged("post_install", "-at_install")
class TestClassification(FiscalCase):
    """A Kenyan basket is mixed: unga and milk are not standard rated."""

    def test_standard_rated_product_is_taxable(self):
        self.assertEqual(self.royco.product_tmpl_id.factor_type, "taxable")

    def test_zero_rated_product_is_zero(self):
        self.assertEqual(self.unga.product_tmpl_id.factor_type, "zero")

    def test_exempt_product_is_exempted(self):
        self.assertEqual(self.milk.product_tmpl_id.factor_type, "exempted")

    def test_classification_follows_the_tax(self):
        """Re-taxing a product must re-classify it."""
        template = self.milk.product_tmpl_id
        template.taxes_id = [(6, 0, [self.tax_standard.id])]
        self.assertEqual(template.factor_type, "taxable")

    def test_two_sales_taxes_are_refused_when_fiscalising(self):
        """A fiscal receipt reports one rate per line."""
        with self.assertRaises(ValidationError):
            self.royco.product_tmpl_id.taxes_id = [
                (6, 0, [self.tax_standard.id, self.tax_zero.id])
            ]

    def test_two_sales_taxes_are_allowed_when_not_fiscalising(self):
        """Installing this module must not break products elsewhere.

        Odoo's own defaults and genuinely multi-taxed products have to keep
        working for companies that do not run a fiscal device.
        """
        self.company.retail_fiscal_enabled = False
        self.royco.product_tmpl_id.taxes_id = [
            (6, 0, [self.tax_standard.id, self.tax_zero.id])
        ]
        self.assertEqual(len(self.royco.product_tmpl_id.taxes_id), 2)

    def test_multi_tax_line_is_refused_at_payload_build(self):
        """The real constraint applies where a receipt is actually built."""
        from odoo.exceptions import UserError

        self.company.retail_fiscal_enabled = False
        self.royco.product_tmpl_id.taxes_id = [
            (6, 0, [self.tax_standard.id, self.tax_zero.id])
        ]
        session = self._open_session()
        order = self._order(session, [(self.royco, 1)])
        self.company.retail_fiscal_enabled = True
        with self.assertRaises(UserError):
            order._build_fiscal_payload()

    def test_untaxed_product_has_no_classification(self):
        template = self.royco.product_tmpl_id
        template.taxes_id = [(5, 0, 0)]
        self.assertFalse(template.factor_type)

    def test_ptu_letters_are_configurable_per_rate(self):
        """PTU letters are assigned per device, so they are data."""
        self.assertEqual(self.tax_standard.fiscal_ptu_value, "B")
        self.assertEqual(self.tax_zero.fiscal_ptu_value, "C")
        self.assertEqual(self.tax_exempt.fiscal_ptu_value, "A")

    def test_exempt_product_falls_back_to_company_hs_code(self):
        """KRA needs an HS code to justify a non-standard rate."""
        session = self._open_session()
        order = self._order(session, [(self.milk, 3)])
        values = order._fiscal_line_values()[0]
        self.assertEqual(
            values["hs_code"], self.company.retail_exemption_hs_code
        )

    def test_product_hs_code_takes_precedence(self):
        session = self._open_session()
        order = self._order(session, [(self.unga, 2)])
        self.assertEqual(order._fiscal_line_values()[0]["hs_code"], "1102.20.00")

    def test_taxable_product_needs_no_hs_code(self):
        session = self._open_session()
        order = self._order(session, [(self.royco, 1)])
        self.assertEqual(order._fiscal_line_values()[0]["hs_code"], "")
