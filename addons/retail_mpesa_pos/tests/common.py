from odoo.tests.common import TransactionCase

CONFIG_PATH = "odoo.addons.retail_mpesa_base.models.mpesa_config.MpesaConfig"


class MpesaPosCase(TransactionCase):
    """A till with a working M-PESA method. Daraja itself is always mocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("retail_mpesa.consumer_key", "test-key")
        params.set_param("retail_mpesa.consumer_secret", "test-secret")
        params.set_param("retail_mpesa.passkey", "test-passkey")

        cls.mpesa_config = cls.env["mpesa.config"].create(
            {
                "name": "Tano Till 174379",
                "shortcode": "174379",
                "environment": "sandbox",
                "callback_base_url": "https://tano.example.com",
            }
        )

        cash_journal = cls.env["account.journal"].create(
            {
                "name": "Tano MPESA Test Cash",
                "type": "cash",
                "code": "TMTC",
                "company_id": cls.env.company.id,
            }
        )
        cls.method_cash = cls.env["pos.payment.method"].create(
            {
                "name": "Cash (mpesa test)",
                "journal_id": cash_journal.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.method_mpesa = cls.env["pos.payment.method"].create(
            {
                "name": "Lipa na M-PESA",
                "retail_mpesa_config_id": cls.mpesa_config.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Westgate Till 4",
                "payment_method_ids": [
                    (6, 0, [cls.method_cash.id, cls.method_mpesa.id])
                ],
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Dettol Antiseptic Liquid 200ml",
                "type": "consu",
                "is_storable": True,
                "available_in_pos": True,
                "list_price": 280.0,
                "taxes_id": [(5, 0, 0)],
            }
        )

    def _open_session(self):
        session = self.env["pos.session"].create({"config_id": self.config.id})
        session.action_pos_session_open()
        return session

    def _order_with_payments(self, session, payments, total):
        """``payments`` is a list of (method, amount, mpesa_receipt_or_None)."""
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "company_id": self.env.company.id,
                "amount_tax": 0.0,
                "amount_total": total,
                "amount_paid": total,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": total,
                            "price_subtotal": total,
                            "price_subtotal_incl": total,
                            "tax_ids": [(5, 0, 0)],
                        },
                    )
                ],
            }
        )
        for method, amount, receipt in payments:
            values = {
                "pos_order_id": order.id,
                "payment_method_id": method.id,
                "amount": amount,
            }
            if receipt:
                values["retail_mpesa_receipt"] = receipt
            self.env["pos.payment"].create(values)
        order.write({"state": "done"})
        return order
