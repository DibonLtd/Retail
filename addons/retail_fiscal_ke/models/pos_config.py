from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    retail_fiscal_printer_id = fields.Many2one(
        comodel_name="fiscal.printer",
        string="Fiscal Printer",
        help="Device this till prints fiscal receipts on.",
    )

    def _retail_fiscal_printer(self):
        """Return the printer for this till, falling back to the company's."""
        self.ensure_one()
        return self.retail_fiscal_printer_id or self.company_id.retail_fiscal_printer_id
