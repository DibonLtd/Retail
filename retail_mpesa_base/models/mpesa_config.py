import base64
import json
import logging
from datetime import datetime, timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DARAJA_HOSTS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}

# Daraja access tokens are valid for an hour; refresh a little early.
TOKEN_SAFETY_MARGIN = timedelta(minutes=5)
REQUEST_TIMEOUT = 30


class MpesaConfig(models.Model):
    _name = "mpesa.config"
    _description = "M-PESA Daraja Configuration"
    _order = "sequence, id"

    name = fields.Char(required=True, default="Lipa na M-PESA")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    environment = fields.Selection(
        selection=[("sandbox", "Sandbox"), ("production", "Production")],
        default="sandbox",
        required=True,
    )
    shortcode = fields.Char(
        string="Business Shortcode",
        required=True,
        help="The till or paybill number, for example 174379.",
    )
    account_reference = fields.Char(
        default="TANO",
        help="Shown to the customer on the STK push prompt.",
    )

    # Credentials are held as parameter keys, never as literal secrets in the
    # database dump or in git. The key names point at ir.config_parameter.
    consumer_key_param = fields.Char(
        default="retail_mpesa.consumer_key",
        required=True,
        help="Name of the ir.config_parameter holding the Daraja consumer key.",
    )
    consumer_secret_param = fields.Char(
        default="retail_mpesa.consumer_secret",
        required=True,
        help="Name of the ir.config_parameter holding the Daraja consumer secret.",
    )
    passkey_param = fields.Char(
        default="retail_mpesa.passkey",
        required=True,
        help="Name of the ir.config_parameter holding the STK push passkey.",
    )

    callback_base_url = fields.Char(
        help=(
            "Public HTTPS base URL Safaricom posts callbacks to. Must be "
            "reachable from the internet and registered with Safaricom."
        )
    )
    credentials_ready = fields.Boolean(compute="_compute_credentials_ready")

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    def _param(self, key_field):
        """Read a secret out of ir.config_parameter."""
        self.ensure_one()
        param_name = self[key_field]
        if not param_name:
            return ""
        return (
            self.env["ir.config_parameter"].sudo().get_param(param_name, default="")
            or ""
        )

    @api.depends("consumer_key_param", "consumer_secret_param", "passkey_param")
    def _compute_credentials_ready(self):
        for config in self:
            config.credentials_ready = bool(
                config._param("consumer_key_param")
                and config._param("consumer_secret_param")
            )

    def _base_url(self):
        self.ensure_one()
        return DARAJA_HOSTS[self.environment]

    # ------------------------------------------------------------------
    # Daraja calls
    # ------------------------------------------------------------------

    def _request(self, method, path, payload=None, auth=None, headers=None):
        """Single seam for every outbound Daraja HTTP call.

        Tests patch this method, so no test ever reaches Safaricom.
        """
        self.ensure_one()
        url = "%s%s" % (self._base_url(), path)
        try:
            response = requests.request(
                method,
                url,
                json=payload,
                auth=auth,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise UserError(
                self.env._("Could not reach Safaricom Daraja: %s", exc)
            ) from exc
        if response.status_code >= 400:
            _logger.warning(
                "Daraja %s %s returned %s: %s",
                method,
                path,
                response.status_code,
                response.text[:500],
            )
            raise UserError(
                self.env._(
                    "Daraja rejected the request (HTTP %(code)s): %(body)s",
                    code=response.status_code,
                    body=response.text[:300],
                )
            )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise UserError(
                self.env._("Daraja returned a non-JSON response.")
            ) from exc

    def _get_access_token(self):
        """Fetch an OAuth token, cached in ir.config_parameter until expiry."""
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        cache_key = "retail_mpesa.token.%s" % self.id
        expiry_key = "retail_mpesa.token_expiry.%s" % self.id

        cached = params.get_param(cache_key)
        expiry = params.get_param(expiry_key)
        if cached and expiry:
            try:
                if datetime.fromisoformat(expiry) > fields.Datetime.now():
                    return cached
            except ValueError:
                pass

        key = self._param("consumer_key_param")
        secret = self._param("consumer_secret_param")
        if not (key and secret):
            raise UserError(
                self.env._(
                    "Daraja credentials are not configured. Set the "
                    "ir.config_parameter entries named on the M-PESA "
                    "configuration."
                )
            )
        result = self._request(
            "GET",
            "/oauth/v1/generate?grant_type=client_credentials",
            auth=(key, secret),
        )
        token = result.get("access_token")
        if not token:
            raise UserError(self.env._("Daraja did not return an access token."))
        lifetime = int(result.get("expires_in", 3599))
        valid_until = (
            fields.Datetime.now() + timedelta(seconds=lifetime) - TOKEN_SAFETY_MARGIN
        )
        params.set_param(cache_key, token)
        params.set_param(expiry_key, valid_until.isoformat())
        return token

    def _stk_password(self, timestamp):
        """Base64 of shortcode + passkey + timestamp, as Daraja requires."""
        self.ensure_one()
        raw = "%s%s%s" % (self.shortcode, self._param("passkey_param"), timestamp)
        return base64.b64encode(raw.encode()).decode()

    @staticmethod
    def _normalise_phone(phone):
        """Convert a Kenyan number to the 2547XXXXXXXX form Daraja expects."""
        digits = "".join(character for character in (phone or "") if character.isdigit())
        if digits.startswith("254"):
            return digits
        if digits.startswith("0"):
            return "254" + digits[1:]
        if len(digits) == 9:
            return "254" + digits
        return digits

    def stk_push(self, phone, amount, reference, description=None):
        """Trigger an STK push and return the created mpesa.transaction."""
        self.ensure_one()
        if not self.callback_base_url:
            raise UserError(
                self.env._(
                    "Set the callback base URL before using STK push. "
                    "Safaricom must be able to reach it over HTTPS."
                )
            )
        msisdn = self._normalise_phone(phone)
        if len(msisdn) != 12:
            raise UserError(
                self.env._("'%s' is not a valid Kenyan mobile number.", phone)
            )

        timestamp = fields.Datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self._stk_password(timestamp),
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(round(amount)),
            "PartyA": msisdn,
            "PartyB": self.shortcode,
            "PhoneNumber": msisdn,
            "CallBackURL": "%s/mpesa/callback/stk" % self.callback_base_url.rstrip("/"),
            "AccountReference": self.account_reference or reference,
            "TransactionDesc": description or reference,
        }
        result = self._request(
            "POST",
            "/mpesa/stkpush/v1/processrequest",
            payload=payload,
            headers={"Authorization": "Bearer %s" % self._get_access_token()},
        )
        return self.env["mpesa.transaction"].create(
            {
                "config_id": self.id,
                "company_id": self.company_id.id,
                "amount": amount,
                "phone": msisdn,
                "reference": reference,
                "checkout_request_id": result.get("CheckoutRequestID"),
                "merchant_request_id": result.get("MerchantRequestID"),
                "state": "pending",
                "raw_request": json.dumps(
                    {key: value for key, value in payload.items() if key != "Password"},
                    indent=2,
                ),
                "raw_response": json.dumps(result, indent=2),
            }
        )
