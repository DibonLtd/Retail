from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import PosReportCase


@tagged("post_install", "-at_install")
class TestPaymentBuckets(PosReportCase):
    """The reporting bucket decides which column a payment method lands in."""

    def test_cash_method_defaults_to_cash_bucket(self):
        self.assertEqual(self.method_cash.retail_payment_bucket, "cash")

    def test_non_cash_method_defaults_to_other(self):
        self.assertEqual(self.method_card.retail_payment_bucket, "other")

    def test_mpesa_bucket_is_explicit(self):
        """M-PESA cannot be auto-detected, so it is set on the method."""
        self.assertEqual(self.method_mpesa.retail_payment_bucket, "mpesa")

    def test_bucket_can_be_overridden(self):
        self.method_card.retail_payment_bucket = "mpesa"
        self.assertEqual(self.method_card.retail_payment_bucket, "mpesa")

    def test_split_payment_records_both_legs(self):
        """TC-POS-04: cash and M-PESA on one order report separately."""
        session = self._open_session()
        # 20 x unga = 2400, settled 1000 cash + 1400 M-PESA.
        self._make_order(
            session,
            [(self.unga, 20)],
            [(self.method_cash, 1000.0), (self.method_mpesa, 1400.0)],
            order_date="2025-01-24 15:00:00",
        )
        report = self._new_report("2025-01-24", "2025-01-24")
        report.action_generate()

        line = report.daily_line_ids
        self.assertEqual(line.cash_amount, 1000.0)
        self.assertEqual(line.mpesa_amount, 1400.0)
        self.assertEqual(
            line.cash_amount + line.mpesa_amount + line.other_amount,
            line.total_sales,
            "Payment legs must reconcile against the day's takings.",
        )

    def test_reversed_date_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._new_report("2025-01-26", "2025-01-20")
