from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    retail_warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        relation="retail_user_warehouse_rel",
        column1="user_id",
        column2="warehouse_id",
        string="Assigned Branches",
        help=(
            "Branches this user may transact against. "
            "Leave empty to allow all branches, which is the usual "
            "setting for head office staff."
        ),
    )

    def _is_warehouse_allowed(self, warehouse):
        """Return True if this user may transact against ``warehouse``.

        An empty assignment is treated as unrestricted so that head office
        roles are not locked out by default.
        """
        self.ensure_one()
        if not self.retail_warehouse_ids:
            return True
        return warehouse in self.retail_warehouse_ids
