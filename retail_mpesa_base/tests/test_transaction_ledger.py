from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def stk_callback(checkout_id, result_code=0, receipt="SHX7YU9823", amount=1295.69):
    """Build a Daraja STK callback payload in Safaricom's exact shape."""
    body = {
        "MerchantRequestID": "29115-34620561-1",
        "CheckoutRequestID": checkout_id,
        "ResultCode": result_code,
        "ResultDesc": "The service request is processed successfully."
        if result_code == 0
        else "Request cancelled by user",
    }
    if result_code == 0:
        body["CallbackMetadata"] = {
            "Item": [
                {"Name": "Amount", "Value": amount},
                {"Name": "MpesaReceiptNumber", "Value": receipt},
                {"Name": "TransactionDate", "Value": 20250129142233},
                {"Name": "PhoneNumber", "Value": 254722123456},
            ]
        }
    return {"Body": {"stkCallback": body}}


@tagged("post_install", "-at_install")
class TestTransactionLedger(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["mpesa.config"].create(
            {"name": "Till 174379", "shortcode": "174379"}
        )

    def _pending(self, checkout_id="ws_CO_1", amount=1295.69):
        return self.env["mpesa.transaction"].create(
            {
                "config_id": self.config.id,
                "checkout_request_id": checkout_id,
                "amount": amount,
                "phone": "254722123456",
                "reference": "POS/2025/00042",
                "state": "pending",
            }
        )

    # -- TC-POS-02 ----------------------------------------------------------

    def test_tc_pos_02_successful_callback_records_receipt(self):
        transaction = self._pending()
        self.env["mpesa.transaction"].process_stk_callback(
            stk_callback("ws_CO_1", receipt="SHX7YU9823", amount=1295.69)
        )
        self.assertEqual(transaction.state, "success")
        self.assertEqual(transaction.receipt_number, "SHX7YU9823")
        self.assertEqual(transaction.amount, 1295.69)
        self.assertTrue(transaction.transaction_date)

    # -- idempotency --------------------------------------------------------

    def test_replayed_callback_does_not_change_state_twice(self):
        """Safaricom retries callbacks; a replay must not double-credit."""
        transaction = self._pending()
        payload = stk_callback("ws_CO_1", receipt="SHX7YU9823")
        self.env["mpesa.transaction"].process_stk_callback(payload)
        first_write = transaction.write_date

        self.env["mpesa.transaction"].process_stk_callback(payload)
        self.assertEqual(transaction.state, "success")
        self.assertEqual(transaction.receipt_number, "SHX7YU9823")
        self.assertEqual(
            transaction.write_date,
            first_write,
            "A replayed callback must leave the record untouched.",
        )

    def test_duplicate_receipt_number_is_refused(self):
        from psycopg2 import IntegrityError

        from odoo.tools import mute_logger

        self._pending("ws_CO_a").write({"receipt_number": "DUP123"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.cr.savepoint():
                self._pending("ws_CO_b").write({"receipt_number": "DUP123"})

    # -- failure paths ------------------------------------------------------

    def test_customer_cancellation_is_recorded(self):
        transaction = self._pending()
        self.env["mpesa.transaction"].process_stk_callback(
            stk_callback("ws_CO_1", result_code=1032)
        )
        self.assertEqual(transaction.state, "cancelled")
        self.assertFalse(transaction.receipt_number)

    def test_timeout_is_recorded(self):
        transaction = self._pending()
        self.env["mpesa.transaction"].process_stk_callback(
            stk_callback("ws_CO_1", result_code=1037)
        )
        self.assertEqual(transaction.state, "timeout")

    def test_other_failure_codes_map_to_failed(self):
        transaction = self._pending()
        self.env["mpesa.transaction"].process_stk_callback(
            stk_callback("ws_CO_1", result_code=2001)
        )
        self.assertEqual(transaction.state, "failed")

    def test_unknown_checkout_id_is_ignored_safely(self):
        result = self.env["mpesa.transaction"].process_stk_callback(
            stk_callback("ws_CO_does_not_exist")
        )
        self.assertFalse(result)

    def test_malformed_callback_is_ignored_safely(self):
        self.assertFalse(
            self.env["mpesa.transaction"].process_stk_callback({"nonsense": True})
        )

    # -- manual entry (US-POS-04 fallback) ----------------------------------

    def test_manual_payment_is_recorded_as_successful(self):
        """A customer paying the till directly never triggers an STK push."""
        transaction = self.env["mpesa.transaction"].record_manual_payment(
            self.config, "RGT5KL2394", 385.0, reference="POS/2025/00001"
        )
        self.assertEqual(transaction.state, "success")
        self.assertEqual(transaction.origin, "manual")
        self.assertEqual(transaction.receipt_number, "RGT5KL2394")

    def test_manual_payment_is_idempotent_on_receipt(self):
        first = self.env["mpesa.transaction"].record_manual_payment(
            self.config, "RGT5KL2394", 385.0
        )
        second = self.env["mpesa.transaction"].record_manual_payment(
            self.config, "RGT5KL2394", 385.0
        )
        self.assertEqual(first, second)

    def test_display_name_prefers_receipt_number(self):
        transaction = self._pending()
        self.assertEqual(transaction.display_name, "POS/2025/00042")
        transaction.receipt_number = "SHX7YU9823"
        transaction.invalidate_recordset(["display_name"])
        self.assertEqual(transaction.display_name, "SHX7YU9823")
