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
        fields_list = super()._load_pos_data_fields(config_id)
        for name in ("retail_mpesa_receipt", "retail_mpesa_transaction_id"):
            if name not in fields_list:
                fields_list.append(name)
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
