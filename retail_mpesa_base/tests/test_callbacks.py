import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .test_transaction_ledger import stk_callback

SAFARICOM_IP = "196.201.214.200"


@tagged("post_install", "-at_install")
class TestCallbackEndpoints(HttpCase):
    """The callback endpoints are public, so their guards are the security."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["mpesa.config"].create(
            {"name": "Till 174379", "shortcode": "174379"}
        )
        # Tests run over localhost, which is not a Safaricom address, so the
        # allowlist is opened deliberately for the duration of the test.
        cls.env["ir.config_parameter"].sudo().set_param(
            "retail_mpesa.callback_ip_allowlist", "*"
        )

    def _post(self, path, payload):
        return self.url_open(
            path,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def _pending(self, checkout_id="ws_CO_http_1"):
        return self.env["mpesa.transaction"].create(
            {
                "config_id": self.config.id,
                "checkout_request_id": checkout_id,
                "amount": 500.0,
                "state": "pending",
            }
        )

    # -- STK ----------------------------------------------------------------

    def test_stk_callback_accepts_and_settles(self):
        transaction = self._pending("ws_CO_http_1")
        response = self._post(
            "/mpesa/callback/stk",
            stk_callback("ws_CO_http_1", receipt="ABC123XYZ", amount=500.0),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 0)
        transaction.invalidate_recordset()
        self.assertEqual(transaction.state, "success")
        self.assertEqual(transaction.receipt_number, "ABC123XYZ")

    def test_stk_callback_acknowledges_unknown_transaction(self):
        """Daraja retries on failure, so an unknown id is still acknowledged."""
        response = self._post(
            "/mpesa/callback/stk", stk_callback("ws_CO_unknown")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 0)

    def test_non_json_body_is_rejected(self):
        response = self.url_open(
            "/mpesa/callback/stk",
            data="this is not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)

    def test_callback_from_unlisted_ip_is_forbidden(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "retail_mpesa.callback_ip_allowlist", SAFARICOM_IP
        )
        try:
            response = self._post(
                "/mpesa/callback/stk", stk_callback("ws_CO_http_1")
            )
            self.assertEqual(
                response.status_code,
                403,
                "Only Safaricom addresses may post callbacks.",
            )
        finally:
            self.env["ir.config_parameter"].sudo().set_param(
                "retail_mpesa.callback_ip_allowlist", "*"
            )

    # -- C2B ----------------------------------------------------------------

    def test_c2b_validation_accepts(self):
        response = self._post(
            "/mpesa/callback/c2b/validation",
            {"TransID": "XYZ1", "TransAmount": "100", "BusinessShortCode": "174379"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 0)

    def test_c2b_confirmation_creates_transaction(self):
        response = self._post(
            "/mpesa/callback/c2b/confirmation",
            {
                "TransID": "RGT5KL2394",
                "TransAmount": "385.00",
                "BusinessShortCode": "174379",
                "MSISDN": "254722123456",
                "BillRefNumber": "TANO",
            },
        )
        self.assertEqual(response.status_code, 200)
        transaction = self.env["mpesa.transaction"].search(
            [("receipt_number", "=", "RGT5KL2394")]
        )
        self.assertEqual(len(transaction), 1)
        self.assertEqual(transaction.state, "success")
        self.assertEqual(transaction.origin, "c2b")
        self.assertEqual(transaction.amount, 385.0)

    def test_c2b_confirmation_is_idempotent(self):
        payload = {
            "TransID": "DUPC2B",
            "TransAmount": "100.00",
            "BusinessShortCode": "174379",
            "MSISDN": "254722123456",
        }
        self._post("/mpesa/callback/c2b/confirmation", payload)
        self._post("/mpesa/callback/c2b/confirmation", payload)
        found = self.env["mpesa.transaction"].search(
            [("receipt_number", "=", "DUPC2B")]
        )
        self.assertEqual(len(found), 1, "A replayed C2B must not duplicate.")

    def test_c2b_unknown_shortcode_is_acknowledged_without_creating(self):
        response = self._post(
            "/mpesa/callback/c2b/confirmation",
            {
                "TransID": "UNKNOWN1",
                "TransAmount": "50.00",
                "BusinessShortCode": "999999",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            self.env["mpesa.transaction"].search(
                [("receipt_number", "=", "UNKNOWN1")]
            )
        )
