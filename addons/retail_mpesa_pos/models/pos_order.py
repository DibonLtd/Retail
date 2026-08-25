from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    retail_mpesa_transaction_ids = fields.One2many(
        comodel_name="mpesa.transaction",
        compute="_compute_retail_mpesa_transaction_ids",
        string="M-PESA Transactions",
    )
    retail_mpesa_references = fields.Char(
        compute="_compute_retail_mpesa_references",
        string="M-PESA References",
        help="Shown on the receipt as 'Paid via MPESA - Ref: ...'.",
    )

    def _compute_retail_mpesa_transaction_ids(self):
        for order in self:
            order.retail_mpesa_transaction_ids = (
                order.payment_ids.retail_mpesa_transaction_id
            )

    def _compute_retail_mpesa_references(self):
        for order in self:
            references = [
                payment.retail_mpesa_receipt
                for payment in order.payment_ids
                if payment.retail_mpesa_receipt
            ]
            order.retail_mpesa_references = ", ".join(references)
