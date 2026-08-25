from odoo import fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _retail_return_window_days(self):
        """Return the configured window, preferring the order's own till."""
        self.ensure_one()
        config = self.config_id
        if config and config.retail_return_window_days:
            return config.retail_return_window_days
        return 0

    def _check_retail_return_window(self):
        """US-POS-07: refuse a return raised outside the allowed window."""
        for order in self:
            window = order._retail_return_window_days()
            if not window:
                continue
            if not order.date_order:
                continue
            age = (fields.Datetime.now() - order.date_order).days
            if age > window:
                raise UserError(
                    self.env._(
                        "Order %(order)s was sold %(age)s days ago, beyond the "
                        "%(window)s day return window for %(config)s.",
                        order=order.name,
                        age=age,
                        window=window,
                        config=order.config_id.display_name,
                    )
                )

    def _refund(self):
        self._check_retail_return_window()
        return super()._refund()
