from odoo import api, models, fields


class PosPayment(models.Model):
    _inherit = "pos.payment"

    retail_mpesa_transaction_id = fields.Many2one(
        comodel_name="mpesa.transaction",
        string="M-PESA Transaction",
        copy=False,
        index=True,
    )
    retail_mpesa_receipt = fields.Char(
        string="M-PESA Reference",
        help="Printed on the customer receipt, for example SHX7YU9823.",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Add the receipt reference to the POS payload, safely.

        An EMPTY list here does not mean "no fields" -- Odoo's read() treats
        an empty field list as "every field", which is what core pos.payment
        relies on. Appending to it would narrow the payload to just the names
        added, stripping pos_order_id and amount, and the payment screen would
        then crash on every payment method with pos_order_id undefined.

        So only extend an explicit list; leave "load everything" alone.
        """
        fields_list = super()._load_pos_data_fields(config_id)
        if not fields_list:
            return fields_list
        fields_list = list(fields_list)
        if "retail_mpesa_receipt" not in fields_list:
            fields_list.append("retail_mpesa_receipt")
        return fields_list

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments._retail_link_mpesa_transaction()
        return payments

    def _retail_link_mpesa_transaction(self):
        """Attach the ledger entry matching this payment's reference.

        The till sends the receipt number with the order; matching it here
        keeps the link correct even when the order is synced late, which is
        what happens when a till has been offline.
        """
        Transaction = self.env["mpesa.transaction"].sudo()
        for payment in self:
            if payment.retail_mpesa_transaction_id or not payment.retail_mpesa_receipt:
                continue
            transaction = Transaction.search(
                [
                    ("receipt_number", "=", payment.retail_mpesa_receipt),
                    ("company_id", "=", payment.company_id.id),
                ],
                limit=1,
            )
            if transaction:
                payment.retail_mpesa_transaction_id = transaction.id
                if not transaction.reference:
                    transaction.reference = payment.pos_order_id.name
