from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    retail_fiscal_enabled = fields.Boolean(
        string="Use Fiscal Printer",
        default=False,
        help="Transmit receipts to an ESD fiscal device.",
    )
    retail_fiscal_printer_id = fields.Many2one(
        comodel_name="fiscal.printer",
        string="Default Fiscal Printer",
    )
    retail_exemption_hs_code = fields.Char(
        string="Default Exemption HS Code",
        default="0001.12.00",
        help="Used when an exempt product carries no HS code of its own.",
    )
