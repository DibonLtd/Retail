from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

CONFIG_PATH = "odoo.addons.retail_mpesa_base.models.mpesa_config.MpesaConfig"


@tagged("post_install", "-at_install")
class TestDarajaClient(TransactionCase):
    """Daraja is mocked at the _request seam. No test reaches Safaricom."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("retail_mpesa.consumer_key", "test-key")
        params.set_param("retail_mpesa.consumer_secret", "test-secret")
        params.set_param("retail_mpesa.passkey", "test-passkey")
        cls.config = cls.env["mpesa.config"].create(
            {
                "name": "Tano Till 174379",
                "shortcode": "174379",
                "environment": "sandbox",
                "callback_base_url": "https://tano.example.com",
            }
        )

    # -- phone normalisation ------------------------------------------------

    def test_phone_normalisation(self):
        cases = {
            "0722123456": "254722123456",
            "254722123456": "254722123456",
            "+254 722 123 456": "254722123456",
            "722123456": "254722123456",
        }
        for supplied, expected in cases.items():
            self.assertEqual(
                self.config._normalise_phone(supplied), expected, "input %s" % supplied
            )

    def test_invalid_phone_is_rejected(self):
        with patch(f"{CONFIG_PATH}._request", return_value={}):
            with self.assertRaises(UserError):
                self.config.stk_push("12", 100.0, "POS/0001")

    # -- credentials --------------------------------------------------------

    def test_credentials_ready_reflects_parameters(self):
        self.assertTrue(self.config.credentials_ready)

    def test_missing_credentials_raise(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "retail_mpesa.consumer_key", ""
        )
        self.config.invalidate_recordset(["credentials_ready"])
        with self.assertRaises(UserError):
            self.config._get_access_token()

    def test_secrets_are_not_stored_on_the_record(self):
        """Only parameter names live on the model, never the secrets."""
        stored = self.config.read()[0]
        self.assertNotIn("test-secret", str(stored))
        self.assertEqual(self.config.consumer_secret_param, "retail_mpesa.consumer_secret")

    # -- token caching ------------------------------------------------------

    def test_access_token_is_cached(self):
        with patch(
            f"{CONFIG_PATH}._request",
            return_value={"access_token": "tok-1", "expires_in": "3599"},
        ) as mocked:
            first = self.config._get_access_token()
            second = self.config._get_access_token()
        self.assertEqual(first, "tok-1")
        self.assertEqual(second, "tok-1")
        self.assertEqual(
            mocked.call_count, 1, "The token must be cached, not refetched."
        )

    # -- STK push -----------------------------------------------------------

    def test_stk_push_creates_pending_transaction(self):
        responses = [
            {"access_token": "tok-2", "expires_in": "3599"},
            {
                "MerchantRequestID": "29115-34620561-1",
                "CheckoutRequestID": "ws_CO_191220191020363925",
                "ResponseCode": "0",
            },
        ]
        with patch(f"{CONFIG_PATH}._request", side_effect=responses):
            transaction = self.config.stk_push("0722123456", 1295.69, "POS/2025/00042")

        self.assertEqual(transaction.state, "pending")
        self.assertEqual(transaction.checkout_request_id, "ws_CO_191220191020363925")
        self.assertEqual(transaction.phone, "254722123456")
        self.assertEqual(transaction.amount, 1295.69)
        self.assertEqual(transaction.origin, "stk_push")

    def test_stk_push_never_logs_the_password(self):
        responses = [
            {"access_token": "tok-3", "expires_in": "3599"},
            {"CheckoutRequestID": "ws_CO_1", "MerchantRequestID": "m-1"},
        ]
        with patch(f"{CONFIG_PATH}._request", side_effect=responses):
            transaction = self.config.stk_push("0722123456", 100.0, "POS/0002")
        self.assertNotIn("Password", transaction.raw_request)

    def test_stk_push_requires_callback_url(self):
        self.config.callback_base_url = False
        with self.assertRaises(UserError):
            self.config.stk_push("0722123456", 100.0, "POS/0003")

    def test_stk_password_is_base64_of_shortcode_passkey_timestamp(self):
        import base64

        timestamp = "20250129142233"
        expected = base64.b64encode(
            ("174379" + "test-passkey" + timestamp).encode()
        ).decode()
        self.assertEqual(self.config._stk_password(timestamp), expected)

    def test_sandbox_and_production_hosts_differ(self):
        self.assertIn("sandbox", self.config._base_url())
        self.config.environment = "production"
        self.assertEqual(self.config._base_url(), "https://api.safaricom.co.ke")
