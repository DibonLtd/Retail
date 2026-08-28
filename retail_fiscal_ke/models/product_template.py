from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .account_tax import FACTOR_TYPES


class ProductTemplate(models.Model):
    _inherit = "product.template"

    factor_type = fields.Selection(
        selection=FACTOR_TYPES,
        string="Fiscal Treatment",
        compute="_compute_factor_type",
        store=True,
        help="Inherited from the product's tax.",
    )
    hscode_index = fields.Char(
        string="HS Code",
        copy=False,
        help="Harmonised System code, required by KRA for exempt and zero-rated supplies.",
    )

    @api.depends("taxes_id", "taxes_id.factor_type")
    def _compute_factor_type(self):
        for product in self:
            taxes = product.taxes_id
            product.factor_type = taxes.factor_type if len(taxes) == 1 else False

    @api.constrains("taxes_id")
    def _check_single_sales_tax(self):
        """A fiscal device reports one rate per line.

        Scoped to companies that actually fiscalise. Enforcing this on every
        product would mean that merely installing this module broke product
        creation everywhere, including Odoo's own defaults and products that
        legitimately carry more than one tax.
        """
        for product in self:
            company = product.company_id or self.env.company
            if not company.retail_fiscal_enabled:
                continue
            if len(product.taxes_id) > 1:
                raise ValidationError(
                    self.env._(
                        "%s has more than one sales tax. A fiscal receipt "
                        "reports a single rate per line, so exactly one tax "
                        "is allowed while fiscal printing is enabled.",
                        product.display_name,
                    )
                )
