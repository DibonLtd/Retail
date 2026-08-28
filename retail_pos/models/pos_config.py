from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    retail_block_zero_qty = fields.Boolean(
        string="Block Out-of-Stock Items",
        default=True,
        help=(
            "Refuse to add a storable product to the cart when the till's "
            "warehouse holds none of it. Prevents selling stock the branch "
            "does not have."
        ),
    )
    retail_return_window_days = fields.Integer(
        string="Return Window (days)",
        default=7,
        help=(
            "How long after the original sale a return may be processed. "
            "Set to 0 to allow returns indefinitely."
        ),
    )
