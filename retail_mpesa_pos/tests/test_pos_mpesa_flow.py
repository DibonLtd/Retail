from odoo.tests import tagged

from .common import MpesaPosCase


@tagged("post_install", "-at_install")
class TestPosMpesaFlow(MpesaPosCase):
    """The receipt reference and the ledger link that make MPESA traceable."""

    def setUp(self):
        super().setUp()
        self.session = self._open_session()

    def test_payment_links_to_its_ledger_entry(self):
        self.method_mpesa.retail_mpesa_record_manual(
            "SHX7YU9823", 280.0, reference="manual"
        )
        order = self._order_with_payments(
            self.session, [(self.method_mpesa, 280.0, "SHX7YU9823")], 280.0
        )
        payment = order.payment_ids
        self.assertTrue(
            payment.retail_mpesa_transaction_id,
            "The payment leg must resolve to its M-PESA transaction.",
        )
        self.assertEqual(
            payment.retail_mpesa_transaction_id.receipt_number, "SHX7YU9823"
        )

    def test_transaction_gains_the_order_reference(self):
        self.method_mpesa.retail_mpesa_record_manual("REFBACK1", 280.0)
        order = self._order_with_payments(
            self.session, [(self.method_mpesa, 280.0, "REFBACK1")], 280.0
        )
        self.assertEqual(
            order.payment_ids.retail_mpesa_transaction_id.reference, order.name
        )

    def test_receipt_shows_the_mpesa_reference(self):
        """US-POS-04: 'Paid via MPESA - Ref: ...' needs this string."""
        self.method_mpesa.retail_mpesa_record_manual("PRINTME1", 280.0)
        order = self._order_with_payments(
            self.session, [(self.method_mpesa, 280.0, "PRINTME1")], 280.0
        )
        self.assertEqual(order.retail_mpesa_references, "PRINTME1")

    def test_split_payment_records_only_the_mpesa_leg_reference(self):
        """TC-POS-04: part cash, part M-PESA."""
        self.method_mpesa.retail_mpesa_record_manual("KGH3RR4590", 1780.0)
        order = self._order_with_payments(
            self.session,
            [
                (self.method_cash, 2000.0, None),
                (self.method_mpesa, 1780.0, "KGH3RR4590"),
            ],
            3780.0,
        )
        self.assertEqual(len(order.payment_ids), 2)
        self.assertEqual(order.retail_mpesa_references, "KGH3RR4590")
        self.assertEqual(sum(order.payment_ids.mapped("amount")), 3780.0)

    def test_payment_without_reference_has_no_transaction(self):
        order = self._order_with_payments(
            self.session, [(self.method_cash, 280.0, None)], 280.0
        )
        self.assertFalse(order.payment_ids.retail_mpesa_transaction_id)
        self.assertFalse(order.retail_mpesa_references)

    def test_unmatched_reference_leaves_the_link_empty(self):
        """A code with no ledger entry must not invent one."""
        order = self._order_with_payments(
            self.session, [(self.method_mpesa, 280.0, "NOSUCHCODE")], 280.0
        )
        self.assertFalse(order.payment_ids.retail_mpesa_transaction_id)
        self.assertEqual(order.retail_mpesa_references, "NOSUCHCODE")

    def test_pos_payment_payload_keeps_pos_order_id(self):
        """Regression: the payment screen dies without pos_order_id.

        Core pos.payment returns an EMPTY field list, which Odoo's read()
        treats as "every field". An override that appends to that list turns
        it into "only these fields", stripping pos_order_id -- and then
        set_amount raises "Cannot read properties of undefined (reading
        'assert_editable')" on every payment method, not just M-PESA.

        This asserts the payload itself rather than the field list, because
        the field list is exactly what misled the original test.
        """
        loaded = self.env["pos.payment"]._load_pos_data_fields(self.config.id)
        # setUp already opened a session; Odoo allows only one per config.
        order = self._order_with_payments(
            self.session, [(self.method_cash, 280.0, None)], 280.0
        )
        payload = order.payment_ids.read(loaded, load=False)[0]

        for required in ("pos_order_id", "payment_method_id", "amount"):
            self.assertIn(
                required,
                payload,
                "%s must reach the POS or the payment screen crashes" % required,
            )
        self.assertIn(
            "retail_mpesa_receipt",
            payload,
            "The receipt reference must reach the POS for the printed receipt.",
        )

    def test_payment_method_payload_keeps_core_fields(self):
        """The same trap on pos.payment.method, which returns an explicit list."""
        loaded = self.env["pos.payment.method"]._load_pos_data_fields(self.config.id)
        self.assertIn("id", loaded)
        self.assertIn("name", loaded)
        self.assertIn("is_cash_count", loaded)
        self.assertIn("retail_mpesa_config_id", loaded)
