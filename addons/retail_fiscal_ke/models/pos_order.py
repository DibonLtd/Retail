from odoo import api, fields, models
from odoo.exceptions import UserError

from . import fiscal_helpers as helpers


class PosOrder(models.Model):
    _inherit = "pos.order"

    fiscal_receipt_no = fields.Char(readonly=True, copy=False, index=True)
    fiscal_log_ids = fields.One2many(
        comodel_name="fiscal.log", inverse_name="pos_order_id", readonly=True
    )
    fiscal_state = fields.Selection(
        selection=[
            ("not_required", "Not Required"),
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
        compute="_compute_fiscal_state",
        store=True,
    )

    @api.depends("company_id.retail_fiscal_enabled", "fiscal_log_ids.state")
    def _compute_fiscal_state(self):
        for order in self:
            if not order.company_id.retail_fiscal_enabled:
                order.fiscal_state = "not_required"
                continue
            logs = order.fiscal_log_ids
            if not logs:
                order.fiscal_state = "pending"
            elif any(log.state == "sent" for log in logs):
                order.fiscal_state = "sent"
            else:
                order.fiscal_state = "failed"

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------

    def _fiscal_line_values(self):
        """Return device-safe values for each sold line.

        Assembling this separately from the wire format keeps the part that
        depends on Odoo data testable without a device attached.
        """
        self.ensure_one()
        values = []
        for line in self.lines:
            product = line.product_id
            tax = line.tax_ids[:1]
            factor = product.product_tmpl_id.factor_type or "exempted"
            hs_code = product.product_tmpl_id.hscode_index
            if factor != "taxable" and not hs_code:
                # KRA requires an HS code to justify a non-standard rate.
                hs_code = self.company_id.retail_exemption_hs_code
            values.append(
                {
                    "name": helpers.trim_item_name(product.name),
                    "quantity": helpers.format_amount(line.qty),
                    "price_unit": helpers.format_amount(line.price_unit),
                    "total": helpers.format_amount(line.price_subtotal_incl),
                    "ptu": tax.fiscal_ptu_value or "A",
                    "factor_type": factor,
                    "hs_code": hs_code or "",
                }
            )
        return values

    def _fiscal_cashier_name(self):
        """Name to print as the cashier.

        pos_hr adds employee_id and is not a dependency of this module, so it
        is read defensively: with pos_hr installed the employee is the real
        cashier, without it the session user is.
        """
        self.ensure_one()
        employee = self._fields.get("employee_id") and self.employee_id
        return (employee.name if employee else "") or self.user_id.name or ""

    def _fiscal_header_values(self):
        self.ensure_one()
        return {
            "reference": helpers.alphanumeric_tail(self.name, 20),
            "cashier": helpers.sanitize(self._fiscal_cashier_name(), 30),
            "customer_pin": self.partner_id.vat or "",
            "total": helpers.format_amount(self.amount_total),
            "tax_total": helpers.format_amount(self.amount_tax),
        }

    def _build_fiscal_payload(self):
        """Assemble the payload sent to the device.

        Deliberately a simple, documented XML envelope rather than a guess at
        the Novitus packet layout. The device-specific format belongs here and
        should be pinned against real hardware before go-live; the surrounding
        classification, logging and transport are complete and tested.
        """
        self.ensure_one()
        header = self._fiscal_header_values()
        parts = [
            "<Receipt>",
            "  <Reference>%s</Reference>" % header["reference"],
            "  <Cashier>%s</Cashier>" % header["cashier"],
            "  <CustomerPIN>%s</CustomerPIN>" % header["customer_pin"],
        ]
        for line in self._fiscal_line_values():
            parts.append(
                '  <Item name="%s" qty="%s" price="%s" total="%s" '
                'ptu="%s" factor="%s" hs="%s"/>'
                % (
                    line["name"],
                    line["quantity"],
                    line["price_unit"],
                    line["total"],
                    line["ptu"],
                    line["factor_type"],
                    line["hs_code"],
                )
            )
        parts.append("  <Total>%s</Total>" % header["total"])
        parts.append("  <TaxTotal>%s</TaxTotal>" % header["tax_total"])
        parts.append("</Receipt>")
        return "\n".join(parts)

    def action_fiscalise(self):
        """Transmit this order to its till's fiscal printer."""
        for order in self:
            if not order.company_id.retail_fiscal_enabled:
                raise UserError(
                    self.env._("Fiscal printing is not enabled for this company.")
                )
            printer = order.config_id._retail_fiscal_printer()
            if not printer:
                raise UserError(
                    self.env._(
                        "No fiscal printer is configured for %s.",
                        order.config_id.display_name,
                    )
                )
            printer.transmit(order._build_fiscal_payload(), pos_order=order)
        return True
