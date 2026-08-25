from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    retail_payment_bucket = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("mpesa", "M-PESA"),
            ("other", "Other"),
        ],
        string="Reporting Bucket",
        compute="_compute_retail_payment_bucket",
        store=True,
        readonly=False,
        help=(
            "Which column this payment method reports under in the POS sales "
            "summary. Cash is detected automatically; set M-PESA explicitly on "
            "Lipa na M-PESA methods. Card and account payments report as Other."
        ),
    )

    @api.depends("is_cash_count")
    def _compute_retail_payment_bucket(self):
        for method in self:
            method.retail_payment_bucket = "cash" if method.is_cash_count else "other"
