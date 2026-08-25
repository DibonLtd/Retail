import logging
import socket

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Fiscal devices are on the shop LAN; a slow reply must not hold a till.
SOCKET_TIMEOUT = 10
RECV_BUFFER = 8192


class FiscalPrinter(models.Model):
    _name = "fiscal.printer"
    _description = "Fiscal Printer (ESD Device)"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    ip_address = fields.Char(string="IP Address", required=True, default="192.168.0.1")
    port = fields.Integer(required=True, default=6001)
    response_type = fields.Selection(
        selection=[
            ("test", "Test"),
            ("enq", "Enquiry"),
            ("get", "Get"),
            ("silent", "Silent"),
            ("display", "Display"),
        ],
        default="enq",
        help="How much the device reports back after a transmission.",
    )
    address = fields.Char(compute="_compute_address", string="Endpoint")

    def _compute_address(self):
        for printer in self:
            if printer.ip_address and printer.port:
                printer.address = "%s:%s" % (printer.ip_address, printer.port)
            else:
                printer.address = ""

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, payload):
        """Write ``payload`` to the device and return its raw reply.

        The single seam through which every byte reaches the hardware. Tests
        patch this method, so no test opens a socket. Keeping the transport
        isolated here is also what allows the device's wire format to be
        swapped without touching the models that build payloads.
        """
        self.ensure_one()
        if not self.ip_address or not self.port:
            raise UserError(
                self.env._(
                    "Fiscal printer %s has no address configured.", self.display_name
                )
            )
        try:
            with socket.create_connection(
                (self.ip_address, self.port), timeout=SOCKET_TIMEOUT
            ) as connection:
                connection.sendall(
                    payload.encode("utf-8") if isinstance(payload, str) else payload
                )
                return connection.recv(RECV_BUFFER).decode("utf-8", errors="replace")
        except OSError as exc:
            # Surfaced rather than swallowed: an untransmitted receipt is a
            # compliance problem, so the cashier must be told.
            raise UserError(
                self.env._(
                    "Could not reach fiscal printer %(printer)s at "
                    "%(address)s: %(error)s",
                    printer=self.display_name,
                    address=self.address,
                    error=exc,
                )
            ) from exc

    def _log_values(self, payload, pos_order=None):
        self.ensure_one()
        return {
            "printer_id": self.id,
            "payload": payload,
            "endpoint": self.address,
            "pos_order_id": pos_order.id if pos_order else False,
            "user_id": self.env.user.id,
        }

    def _record_failure(self, payload, error, pos_order=None):
        """Record a failed transmission on an independent cursor.

        Raising rolls back the transaction that would have held the audit
        row, so a receipt that never reached the device would leave no trace
        at all. An untransmitted receipt is a compliance problem, so the
        trail has to outlive the failure that caused it.
        """
        self.ensure_one()
        values = dict(
            self._log_values(payload, pos_order),
            state="failed",
            error_response=str(error),
        )
        try:
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, self.env.context)
                env["fiscal.log"].create(values)
                return
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Could not record fiscal failure out of band; "
                "falling back to the current transaction"
            )
        try:
            # Best effort. This row shares the caller's transaction, so it is
            # lost if the caller rolls back, but a partial trail beats none.
            self.env["fiscal.log"].create(values)
        except Exception:  # noqa: BLE001
            # Never let audit logging mask the original device failure.
            _logger.exception("Could not record fiscal transmission failure")

    def transmit(self, payload, pos_order=None):
        """Send a payload and record the exchange in the fiscal log."""
        self.ensure_one()
        try:
            response = self._send(payload)
        except UserError as exc:
            self._record_failure(payload, exc, pos_order=pos_order)
            raise
        return self.env["fiscal.log"].create(
            dict(
                self._log_values(payload, pos_order),
                state="sent",
                response=response,
            )
        )

    def action_test_connection(self):
        """Prove the device is reachable before a shift starts."""
        self.ensure_one()
        self._send("<TEST/>")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._("Fiscal printer %s responded.", self.display_name),
                "sticky": False,
            },
        }
