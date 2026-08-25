from odoo import api, fields, models
from odoo.exceptions import UserError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    retail_mpesa_config_id = fields.Many2one(
        comodel_name="mpesa.config",
        string="M-PESA Configuration",
        help="Linking a Daraja configuration turns this into an M-PESA method.",
    )
    retail_mpesa_allow_stk = fields.Boolean(
        string="Offer STK Push",
        default=True,
        help=(
            "Let the cashier push a payment prompt to the customer's phone. "
            "Manual reference entry stays available either way, because a "
            "customer paying the till from their own handset never triggers "
            "a push."
        ),
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Ship the M-PESA flags to the till.

        pos.payment.method declares an explicit field list, so without this
        the front end would see retail_mpesa_config_id as undefined and would
        never open the M-PESA popup.
        """
        fields_list = super()._load_pos_data_fields(config_id)
        for name in ("retail_mpesa_config_id", "retail_mpesa_allow_stk"):
            if name not in fields_list:
                fields_list.append(name)
        return fields_list

    @api.onchange("retail_mpesa_config_id")
    def _onchange_retail_mpesa_config_id(self):
        """An M-PESA method must report in the M-PESA column."""
        for method in self:
            if method.retail_mpesa_config_id:
                method.retail_payment_bucket = "mpesa"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("retail_mpesa_config_id"):
                vals.setdefault("retail_payment_bucket", "mpesa")
        return super().create(vals_list)

    def _retail_mpesa_config(self):
        self.ensure_one()
        config = self.retail_mpesa_config_id
        if not config:
            raise UserError(
                self.env._(
                    "Payment method %s is not linked to an M-PESA configuration.",
                    self.display_name,
                )
            )
        return config

    # ------------------------------------------------------------------
    # Called from the POS front end
    # ------------------------------------------------------------------

    def retail_mpesa_stk_push(self, phone, amount, reference):
        """Push a payment prompt to the customer's phone.

        Returns the identifiers the till needs to poll for the outcome.
        """
        self.ensure_one()
        config = self._retail_mpesa_config()
        if not self.retail_mpesa_allow_stk:
            raise UserError(
                self.env._("STK push is disabled for %s.", self.display_name)
            )
        transaction = config.stk_push(phone, amount, reference)
        return {
            "transaction_id": transaction.id,
            "checkout_request_id": transaction.checkout_request_id,
            "state": transaction.state,
        }

    def retail_mpesa_poll(self, checkout_request_id):
        """Report the current state of a pushed payment."""
        self.ensure_one()
        transaction = self.env["mpesa.transaction"].search(
            [("checkout_request_id", "=", checkout_request_id)], limit=1
        )
        if not transaction:
            return {"state": "unknown"}
        return {
            "transaction_id": transaction.id,
            "state": transaction.state,
            "receipt_number": transaction.receipt_number or "",
            "result_description": transaction.result_description or "",
        }

    def retail_mpesa_record_manual(self, receipt_number, amount, reference=None):
        """Record a code the customer read out after paying the till directly."""
        self.ensure_one()
        config = self._retail_mpesa_config()
        cleaned = (receipt_number or "").strip().upper()
        if not cleaned:
            raise UserError(self.env._("Enter the M-PESA confirmation code."))
        transaction = self.env["mpesa.transaction"].record_manual_payment(
            config, cleaned, amount, reference=reference
        )
        return {
            "transaction_id": transaction.id,
            "state": transaction.state,
            "receipt_number": transaction.receipt_number,
        }
