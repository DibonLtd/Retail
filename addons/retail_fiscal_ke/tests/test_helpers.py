from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.retail_fiscal_ke.models import fiscal_helpers as helpers


@tagged("post_install", "-at_install")
class TestFiscalHelpers(TransactionCase):
    """Devices reject stray characters and silently truncate long fields."""

    def test_amounts_are_absolute_and_two_decimal(self):
        self.assertEqual(helpers.format_amount(1295.6), "1295.60")
        self.assertEqual(helpers.format_amount(-45.0), "45.00")
        self.assertEqual(helpers.format_amount(0), "0.00")
        self.assertEqual(helpers.format_amount(None), "0.00")

    def test_sanitize_strips_rejected_characters(self):
        self.assertEqual(
            helpers.sanitize("Bidii Unga (Maize) #2kg!"), "Bidii Unga Maize 2kg"
        )

    def test_sanitize_keeps_full_stops(self):
        self.assertEqual(helpers.sanitize("Milk 0.5L"), "Milk 0.5L")

    def test_sanitize_trims_to_length(self):
        self.assertEqual(len(helpers.sanitize("x" * 100)), 40)

    def test_sanitize_handles_empty(self):
        self.assertEqual(helpers.sanitize(None), "")
        self.assertEqual(helpers.sanitize(""), "")

    def test_alphanumeric_tail_keeps_the_distinguishing_end(self):
        """POS/2025/00042 matters in its tail, not its prefix."""
        self.assertEqual(helpers.alphanumeric_tail("POS/2025/00042", 8), "202500042"[-8:])
        self.assertEqual(helpers.alphanumeric_tail("RSR/2025/00042", 5), "00042")

    def test_alphanumeric_tail_handles_empty(self):
        self.assertEqual(helpers.alphanumeric_tail("", 5), "")

    def test_trim_item_name_marks_truncation(self):
        """Silent truncation would put two products under one description."""
        long_name = "Brookside Full Cream Long Life Milk 500ml Tetra Pack Carton"
        trimmed = helpers.trim_item_name(long_name)
        self.assertEqual(len(trimmed), 40)
        self.assertTrue(trimmed.endswith(".."))

    def test_trim_item_name_leaves_short_names_alone(self):
        self.assertEqual(
            helpers.trim_item_name("Royco Mchuzi Mix 200g"), "Royco Mchuzi Mix 200g"
        )
