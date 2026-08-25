import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Safaricom publishes the IP ranges its callbacks originate from. Only these
# may post to the endpoints below. Override with the
# retail_mpesa.callback_ip_allowlist system parameter (comma separated); set it
# to "*" only in a sandbox, never in production.
DEFAULT_SAFARICOM_IPS = (
    "196.201.214.200",
    "196.201.214.206",
    "196.201.213.114",
    "196.201.214.207",
    "196.201.214.208",
    "196.201.213.44",
    "196.201.212.127",
    "196.201.212.138",
    "196.201.212.129",
    "196.201.212.136",
    "196.201.212.74",
    "196.201.212.69",
)

# Daraja expects this shape back, and treats anything else as a failed
# delivery, which makes it retry.
ACCEPTED = {"ResultCode": 0, "ResultDesc": "Accepted"}
REJECTED = {"ResultCode": 1, "ResultDesc": "Rejected"}


class MpesaController(http.Controller):
    """Endpoints Safaricom posts to. Public by necessity, guarded by IP."""

    def _caller_allowed(self):
        allowlist = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("retail_mpesa.callback_ip_allowlist", default="")
        )
        if allowlist.strip() == "*":
            _logger.warning(
                "M-PESA callback IP allowlist is '*'. Acceptable in a sandbox, "
                "never in production."
            )
            return True
        allowed = (
            {ip.strip() for ip in allowlist.split(",") if ip.strip()}
            or set(DEFAULT_SAFARICOM_IPS)
        )
        remote = request.httprequest.remote_addr
        if remote not in allowed:
            _logger.warning("Rejected M-PESA callback from unlisted address %s", remote)
            return False
        return True

    def _payload(self):
        try:
            raw = request.httprequest.get_data(as_text=True)
            return json.loads(raw or "{}")
        except (ValueError, json.JSONDecodeError):
            _logger.warning("M-PESA callback carried a non-JSON body")
            return None

    @http.route(
        "/mpesa/callback/stk",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def stk_callback(self, **kwargs):
        """STK push result callback."""
        if not self._caller_allowed():
            return request.make_json_response(REJECTED, status=403)
        payload = self._payload()
        if payload is None:
            return request.make_json_response(REJECTED, status=400)

        transaction = (
            request.env["mpesa.transaction"].sudo().process_stk_callback(payload)
        )
        if not transaction:
            # Acknowledge anyway: retrying will not make an unknown
            # CheckoutRequestID become known, and Daraja retries on failure.
            _logger.info("STK callback did not match any pending transaction")
        return request.make_json_response(ACCEPTED)

    @http.route(
        "/mpesa/callback/c2b/validation",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def c2b_validation(self, **kwargs):
        """C2B validation. Accepting means the payment may proceed."""
        if not self._caller_allowed():
            return request.make_json_response(REJECTED, status=403)
        if self._payload() is None:
            return request.make_json_response(REJECTED, status=400)
        return request.make_json_response(ACCEPTED)

    @http.route(
        "/mpesa/callback/c2b/confirmation",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def c2b_confirmation(self, **kwargs):
        """C2B confirmation: the customer paid the till directly."""
        if not self._caller_allowed():
            return request.make_json_response(REJECTED, status=403)
        payload = self._payload()
        if payload is None:
            return request.make_json_response(REJECTED, status=400)

        receipt = payload.get("TransID")
        if not receipt:
            return request.make_json_response(ACCEPTED)

        Transaction = request.env["mpesa.transaction"].sudo()
        existing = Transaction.search([("receipt_number", "=", receipt)], limit=1)
        if existing:
            return request.make_json_response(ACCEPTED)

        config = (
            request.env["mpesa.config"]
            .sudo()
            .search([("shortcode", "=", payload.get("BusinessShortCode"))], limit=1)
        )
        if not config:
            _logger.warning(
                "C2B confirmation for unknown shortcode %s",
                payload.get("BusinessShortCode"),
            )
            return request.make_json_response(ACCEPTED)

        Transaction.create(
            {
                "config_id": config.id,
                "company_id": config.company_id.id,
                "receipt_number": receipt,
                "amount": float(payload.get("TransAmount") or 0.0),
                "phone": payload.get("MSISDN"),
                "reference": payload.get("BillRefNumber"),
                "state": "success",
                "origin": "c2b",
                "result_code": 0,
                "result_description": "C2B confirmation",
                "callback_payload": json.dumps(payload, indent=2),
            }
        )
        return request.make_json_response(ACCEPTED)
