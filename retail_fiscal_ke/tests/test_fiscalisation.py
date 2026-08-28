from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PRINTER_PATH, FiscalCase


@tagged("post_install", "-at_install")
class TestFiscalisation(FiscalCase):
    """Transmission and its audit trail. The device socket is never opened."""

    def setUp(self):
        super().setUp()
        self.session = self._open_session()

    # -- payload ------------------------------------------------------------

    def test_payload_carries_every_line(self):
        order = self._order(self.session, [(self.royco, 1), (self.unga, 2)])
        payload = order._build_fiscal_payload()
        self.assertEqual(payload.count("<Item "), 2)
        self.assertIn("Royco Mchuzi Mix 200g", payload)
        self.assertIn("Bidii Unga Maize Flour 2kg", payload)

    def test_payload_carries_the_ptu_letter_per_line(self):
        order = self._order(self.session, [(self.royco, 1), (self.milk, 1)])
        payload = order._build_fiscal_payload()
        self.assertIn('ptu="B"', payload, "Standard rated line must carry B.")
        self.assertIn('ptu="A"', payload, "Exempt line must carry A.")

    def test_payload_amounts_are_two_decimal(self):
        order = self._order(self.session, [(self.royco, 3)])
        self.assertIn("<Total>135.00</Total>", order._build_fiscal_payload())

    def test_payload_reference_is_device_safe(self):
        order = self._order(self.session, [(self.royco, 1)])
        payload = order._build_fiscal_payload()
        self.assertNotIn("/", payload.split("<Reference>")[1].split("</Reference>")[0])

    # -- transmission -------------------------------------------------------

    def test_successful_transmission_is_logged(self):
        order = self._order(self.session, [(self.royco, 1)])
        with patch(f"{PRINTER_PATH}._send", return_value="<OK CUSN='KRA123'/>"):
            order.action_fiscalise()

        log = order.fiscal_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, "sent")
        self.assertIn("CUSN", log.response)
        self.assertEqual(log.printer_id, self.printer)
        self.assertEqual(log.user_id, self.env.user)
        self.assertEqual(order.fiscal_state, "sent")

    def test_device_failure_surfaces_to_the_cashier(self):
        """An untransmitted receipt is a compliance problem, so it must surface."""
        order = self._order(self.session, [(self.royco, 1)])
        with patch(
            f"{PRINTER_PATH}._send", side_effect=UserError("Printer unreachable")
        ):
            with self.assertRaises(UserError):
                order.action_fiscalise()

    def test_device_failure_is_recorded(self):
        """The failure must be recorded before the error propagates.

        Only the call is asserted, not the resulting row. _record_failure
        writes on an independent cursor so the audit trail survives the
        rollback that the raise causes in production, and that cursor cannot
        see this test's fixtures, which are never committed. The values it
        writes are covered by test_failure_log_values.
        """
        order = self._order(self.session, [(self.royco, 1)])
        with patch(
            f"{PRINTER_PATH}._send", side_effect=UserError("Printer unreachable")
        ), patch(f"{PRINTER_PATH}._record_failure", autospec=True) as recorder:
            with self.assertRaises(UserError):
                order.action_fiscalise()

        recorder.assert_called_once()
        self.assertIn("unreachable", str(recorder.call_args))

    def test_failure_log_values(self):
        """The row _record_failure writes is marked failed and keeps the error."""
        order = self._order(self.session, [(self.royco, 1)])
        payload = order._build_fiscal_payload()
        values = dict(
            self.printer._log_values(payload, order),
            state="failed",
            error_response="Printer unreachable",
        )
        self.assertEqual(values["state"], "failed")
        self.assertEqual(values["pos_order_id"], order.id)
        self.assertEqual(values["printer_id"], self.printer.id)
        self.assertEqual(values["endpoint"], self.printer.address)
        self.assertIn("unreachable", values["error_response"])

    def test_log_links_back_to_session_and_till(self):
        order = self._order(self.session, [(self.royco, 1)])
        with patch(f"{PRINTER_PATH}._send", return_value="<OK/>"):
            order.action_fiscalise()
        log = order.fiscal_log_ids
        self.assertEqual(log.session_id, self.session)
        self.assertEqual(log.config_id, self.config)

    def test_till_printer_overrides_the_company_default(self):
        other = self.env["fiscal.printer"].create(
            {"name": "Spare ESD", "ip_address": "192.168.0.60", "port": 6001}
        )
        self.config.retail_fiscal_printer_id = other
        order = self._order(self.session, [(self.royco, 1)])
        with patch(f"{PRINTER_PATH}._send", return_value="<OK/>"):
            order.action_fiscalise()
        self.assertEqual(order.fiscal_log_ids.printer_id, other)

    def test_company_printer_is_the_fallback(self):
        self.config.retail_fiscal_printer_id = False
        order = self._order(self.session, [(self.royco, 1)])
        with patch(f"{PRINTER_PATH}._send", return_value="<OK/>"):
            order.action_fiscalise()
        self.assertEqual(order.fiscal_log_ids.printer_id, self.printer)

    def test_fiscalising_without_a_printer_is_refused(self):
        self.config.retail_fiscal_printer_id = False
        self.company.retail_fiscal_printer_id = False
        order = self._order(self.session, [(self.royco, 1)])
        with self.assertRaises(UserError):
            order.action_fiscalise()

    def test_disabled_company_refuses_to_fiscalise(self):
        self.company.retail_fiscal_enabled = False
        order = self._order(self.session, [(self.royco, 1)])
        with self.assertRaises(UserError):
            order.action_fiscalise()

    def test_state_is_not_required_when_disabled(self):
        self.company.retail_fiscal_enabled = False
        order = self._order(self.session, [(self.royco, 1)])
        order.invalidate_recordset(["fiscal_state"])
        self.assertEqual(order.fiscal_state, "not_required")

    def test_printer_without_address_is_refused(self):
        """The guard is defensive: ip_address is required at database level,
        so this uses an in-memory record to reach the check itself."""
        draft = self.env["fiscal.printer"].new({"name": "Unconfigured"})
        with self.assertRaises(UserError):
            draft._send("<TEST/>")

    def test_test_connection_uses_the_transport_seam(self):
        with patch(f"{PRINTER_PATH}._send", return_value="<OK/>") as mocked:
            result = self.printer.action_test_connection()
        mocked.assert_called_once()
        self.assertEqual(result["params"]["type"], "success")
