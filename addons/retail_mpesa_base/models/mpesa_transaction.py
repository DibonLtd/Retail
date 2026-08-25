import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Daraja STK result codes. 0 is success; the rest are the ones worth naming.
RESULT_CODE_SUCCESS = 0
RESULT_CODE_CANCELLED = 1032
RESULT_CODE_TIMEOUT = 1037
RESULT_CODE_INSUFFICIENT = 1


class MpesaTransaction(models.Model):
    _name = "mpesa.transaction"
    _description = "M-PESA Transaction"
    _order = "create_date desc, id desc"
    _rec_name = "receipt_number"

    config_id = fields.Many2one(
        comodel_name="mpesa.config", string="M-PESA Configuration", required=True
    )
    company_id = fields.Many2one(
        comodel_name="res.company", required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    receipt_number = fields.Char(
        string="M-PESA Receipt",
        index=True,
        help="The confirmation code Safaricom issues, for example SHX7YU9823.",
    )
    checkout_request_id = fields.Char(index=True, copy=False)
    merchant_request_id = fields.Char(copy=False)
    reference = fields.Char(help="Our own reference, usually the POS order name.")

    amount = fields.Monetary(currency_field="currency_id", required=True)
    phone = fields.Char(string="Phone Number")
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("success", "Successful"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled by Customer"),
            ("timeout", "Timed Out"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    result_code = fields.Integer(copy=False)
    result_description = fields.Char(copy=False)
    transaction_date = fields.Datetime(copy=False)

    origin = fields.Selection(
        selection=[
            ("stk_push", "STK Push"),
            ("manual", "Manually Entered"),
            ("c2b", "Customer Initiated (C2B)"),
        ],
        default="stk_push",
        required=True,
        help=(
            "How the payment reached us. Manual entry covers a customer who "
            "paid the till directly from their own handset."
        ),
    )

    raw_request = fields.Text(readonly=True, copy=False)
    raw_response = fields.Text(readonly=True, copy=False)
    callback_payload = fields.Text(readonly=True, copy=False)

    _sql_constraints = [
        (
            "receipt_number_unique",
            "UNIQUE(receipt_number, company_id)",
            "This M-PESA receipt number has already been recorded.",
        ),
    ]

    @api.depends("receipt_number", "reference")
    def _compute_display_name(self):
        for transaction in self:
            transaction.display_name = (
                transaction.receipt_number
                or transaction.reference
                or self.env._("Pending M-PESA payment")
            )

    # ------------------------------------------------------------------
    # Callback handling
    # ------------------------------------------------------------------

    @api.model
    def _state_for_result_code(self, code):
        if code == RESULT_CODE_SUCCESS:
            return "success"
        if code == RESULT_CODE_CANCELLED:
            return "cancelled"
        if code == RESULT_CODE_TIMEOUT:
            return "timeout"
        return "failed"

    @api.model
    def process_stk_callback(self, payload):
        """Apply an STK push callback.

        Idempotent on ``checkout_request_id``: Safaricom retries callbacks, and
        a replay must never credit an order twice. Returns the transaction, or
        an empty recordset when the callback refers to something unknown.
        """
        body = (payload or {}).get("Body", {}).get("stkCallback", {})
        checkout_id = body.get("CheckoutRequestID")
        if not checkout_id:
            _logger.warning("M-PESA callback with no CheckoutRequestID: %s", payload)
            return self.browse()

        transaction = self.sudo().search(
            [("checkout_request_id", "=", checkout_id)], limit=1
        )
        if not transaction:
            _logger.warning(
                "M-PESA callback for unknown CheckoutRequestID %s", checkout_id
            )
            return self.browse()

        if transaction.state != "pending":
            # Already settled. Record the replay but change nothing.
            _logger.info(
                "Ignoring replayed M-PESA callback for %s (state %s)",
                checkout_id,
                transaction.state,
            )
            return transaction

        code = int(body.get("ResultCode", -1))
        values = {
            "result_code": code,
            "result_description": body.get("ResultDesc"),
            "state": self._state_for_result_code(code),
            "callback_payload": json.dumps(payload, indent=2),
        }

        for item in body.get("CallbackMetadata", {}).get("Item", []):
            name = item.get("Name")
            value = item.get("Value")
            if name == "MpesaReceiptNumber" and value:
                values["receipt_number"] = value
            elif name == "Amount" and value is not None:
                values["amount"] = value
            elif name == "PhoneNumber" and value:
                values["phone"] = str(value)
            elif name == "TransactionDate" and value:
                values["transaction_date"] = self._parse_daraja_date(value)

        transaction.sudo().write(values)
        return transaction

    @api.model
    def _parse_daraja_date(self, value):
        """Daraja sends timestamps as the integer 20250129142233."""
        try:
            return fields.Datetime.to_datetime(
                fields.Datetime.from_string(
                    "%s-%s-%s %s:%s:%s"
                    % (
                        str(value)[0:4],
                        str(value)[4:6],
                        str(value)[6:8],
                        str(value)[8:10],
                        str(value)[10:12],
                        str(value)[12:14],
                    )
                )
            )
        except (ValueError, IndexError, TypeError):
            _logger.warning("Unparseable Daraja TransactionDate: %r", value)
            return False

    @api.model
    def record_manual_payment(self, config, receipt_number, amount, reference=None):
        """Record a payment the customer made to the till themselves.

        Most Kenyan till payments never involve an STK push: the customer pays
        from their own handset and reads the code out. This is that path.
        """
        existing = self.sudo().search(
            [
                ("receipt_number", "=", receipt_number),
                ("company_id", "=", config.company_id.id),
            ],
            limit=1,
        )
        if existing:
            return existing
        return self.create(
            {
                "config_id": config.id,
                "company_id": config.company_id.id,
                "receipt_number": receipt_number,
                "amount": amount,
                "reference": reference,
                "state": "success",
                "origin": "manual",
                "result_code": RESULT_CODE_SUCCESS,
                "result_description": "Manually recorded at the till",
            }
        )
