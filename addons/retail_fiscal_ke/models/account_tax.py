from odoo import fields, models

# The letter the fiscal device uses to identify a tax rate. Kenyan devices
# conventionally use A for exempt, B for standard 16%, C for zero rated and
# E for the reduced rate. The letters are configuration, not code, because
# they are assigned per device.
FACTOR_TYPES = [
    ("taxable", "Taxable"),
    ("exempted", "Exempted"),
    ("zero", "Zero Rated"),
]


class AccountTax(models.Model):
    _inherit = "account.tax"

    fiscal_ptu_value = fields.Char(
        string="PTU Value",
        size=2,
        default="A",
        help="Letter the fiscal device uses for this rate, for example B for 16%.",
    )
    factor_type = fields.Selection(
        selection=FACTOR_TYPES,
        string="Fiscal Treatment",
        default="exempted",
        help=(
            "How KRA treats supplies carrying this tax. A Kenyan supermarket "
            "basket is mixed: maize flour and milk are not standard rated."
        ),
    )
