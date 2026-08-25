from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CONFIG_PATH, MpesaPosCase


@tagged("post_install", "-at_install")
class TestMpesaPaymentMethod(MpesaPosCase):
    """US-POS-04: the till's two routes to an M-PESA payment."""

    def test_linking_a_config_sets_the_reporting_bucket(self):
        """An M-PESA method must land in the report's M-PESA column."""
        self.assertEqual(self.method_mpesa.retail_payment_bucket, "mpesa")

    def test_cash_method_is_not_mpesa(self):
        self.assertFalse(self.method_cash.retail_mpesa_config_id)
        self.assertEqual(self.method_cash.retail_payment_bucket, "cash")

    def test_method_without_config_refuses_to_push(self):
        with self.assertRaises(UserError):
            self.method_cash.retail_mpesa_stk_push("0722123456", 100.0, "POS/1")

    # -- STK push -----------------------------------------------------------

    def test_stk_push_returns_polling_identifiers(self):
        responses = [
            {"access_token": "tok", "expires_in": "3599"},
            {"CheckoutRequestID": "ws_CO_pos_1", "MerchantRequestID": "m-1"},
        ]
        with patch(f"{CONFIG_PATH}._request", side_effect=responses):
            result = self.method_mpesa.retail_mpesa_stk_push(
                "0722123456", 1295.69, "POS/2025/00042"
            )
        self.assertEqual(result["checkout_request_id"], "ws_CO_pos_1")
        self.assertEqual(result["state"], "pending")

    def test_stk_push_can_be_disabled(self):
        self.method_mpesa.retail_mpesa_allow_stk = False
        with self.assertRaises(UserError):
            self.method_mpesa.retail_mpesa_stk_push("0722123456", 100.0, "POS/1")

    def test_poll_reports_pending_then_success(self):
        responses = [
            {"access_token": "tok", "expires_in": "3599"},
            {"CheckoutRequestID": "ws_CO_pos_2", "MerchantRequestID": "m-2"},
        ]
        with patch(f"{CONFIG_PATH}._request", side_effect=responses):
            self.method_mpesa.retail_mpesa_stk_push("0722123456", 500.0, "POS/2")

        self.assertEqual(
            self.method_mpesa.retail_mpesa_poll("ws_CO_pos_2")["state"], "pending"
        )

        self.env["mpesa.transaction"].process_stk_callback(
            {
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": "ws_CO_pos_2",
                        "ResultCode": 0,
                        "ResultDesc": "Success",
                        "CallbackMetadata": {
                            "Item": [
                                {"Name": "MpesaReceiptNumber", "Value": "POSREF001"},
                                {"Name": "Amount", "Value": 500.0},
                            ]
                        },
                    }
                }
            }
        )
        polled = self.method_mpesa.retail_mpesa_poll("ws_CO_pos_2")
        self.assertEqual(polled["state"], "success")
        self.assertEqual(polled["receipt_number"], "POSREF001")

    def test_poll_for_unknown_checkout_is_reported_as_unknown(self):
        self.assertEqual(
            self.method_mpesa.retail_mpesa_poll("nope")["state"], "unknown"
        )

    # -- manual entry -------------------------------------------------------

    def test_manual_entry_records_a_successful_payment(self):
        """TC-POS-02 style: the customer reads out the confirmation code."""
        result = self.method_mpesa.retail_mpesa_record_manual(
            "shx7yu9823", 1295.69, reference="POS/2025/00042"
        )
        self.assertEqual(result["state"], "success")
        self.assertEqual(
            result["receipt_number"], "SHX7YU9823", "Codes are normalised to upper case."
        )

    def test_manual_entry_rejects_an_empty_code(self):
        with self.assertRaises(UserError):
            self.method_mpesa.retail_mpesa_record_manual("   ", 100.0)

    def test_manual_entry_is_idempotent(self):
        first = self.method_mpesa.retail_mpesa_record_manual("RGT5KL2394", 385.0)
        second = self.method_mpesa.retail_mpesa_record_manual("RGT5KL2394", 385.0)
        self.assertEqual(first["transaction_id"], second["transaction_id"])

    # -- front-end payload --------------------------------------------------

    def test_mpesa_flags_reach_the_pos_front_end(self):
        """The payment screen keys off these, so they must be loaded.

        pos.payment.method declares an explicit field list upstream, so this
        is the tripwire if the override is ever lost.
        """
        loaded = self.env["pos.payment.method"]._load_pos_data_fields(self.config.id)
        self.assertIn("retail_mpesa_config_id", loaded)
        self.assertIn("retail_mpesa_allow_stk", loaded)
