from odoo import fields, models


class RetailApprovalThreshold(models.Model):
    """An amount band that requires approval from a particular group.

    Approval requirements are held as data so that changing the bands is a
    configuration change rather than a code change.
    """

    _name = "retail.approval.threshold"
    _description = "Retail Purchase Approval Threshold"
    _order = "sequence, amount_from"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    amount_from = fields.Monetary(
        string="Applies From",
        currency_field="currency_id",
        required=True,
        help="This approval is required once the order total reaches this amount.",
    )
    group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Approving Group",
        required=True,
        ondelete="cascade",
    )

    def _matches(self, amount):
        """Return the subset of thresholds triggered by ``amount``."""
        return self.filtered(lambda threshold: amount >= threshold.amount_from)
