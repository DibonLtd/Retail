from odoo.tests import tagged

from .common import PosReportCase


@tagged("post_install", "-at_install")
class TestReportGeneration(PosReportCase):
    """US-RPT-01 and US-RPT-04: daily summary, ranking, and item breakdown."""

    def test_generate_sets_state(self):
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()
        self.assertEqual(report.state, "generated")

    def test_reference_is_generated(self):
        report = self._new_report("2025-01-20", "2025-01-26")
        self.assertTrue(report.name.startswith("PSR/"))

    def test_daily_line_totals_and_payment_split(self):
        session = self._open_session()
        # 2 x unga (240) + 3 x milk (195) = 435, paid 200 cash + 235 M-PESA.
        self._make_order(
            session,
            [(self.unga, 2), (self.milk, 3)],
            [(self.method_cash, 200.0), (self.method_mpesa, 235.0)],
            order_date="2025-01-24 09:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()

        self.assertEqual(len(report.daily_line_ids), 1)
        line = report.daily_line_ids
        self.assertEqual(line.total_sales, 435.0)
        self.assertEqual(line.cash_amount, 200.0)
        self.assertEqual(line.mpesa_amount, 235.0)
        self.assertEqual(line.other_amount, 0.0)

    def test_card_payments_report_as_other(self):
        session = self._open_session()
        self._make_order(
            session,
            [(self.milk, 1)],
            [(self.method_card, 65.0)],
            order_date="2025-01-22 12:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()
        self.assertEqual(report.daily_line_ids.other_amount, 65.0)

    def test_rank_one_is_the_best_day(self):
        session = self._open_session()
        self._make_order(
            session, [(self.unga, 1)], [(self.method_cash, 120.0)],
            order_date="2025-01-21 10:00:00",
        )
        self._make_order(
            session, [(self.unga, 10)], [(self.method_cash, 1200.0)],
            order_date="2025-01-24 10:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()

        by_date = {line.date.isoformat(): line for line in report.daily_line_ids}
        self.assertEqual(by_date["2025-01-24"].rank, 1)
        self.assertEqual(by_date["2025-01-21"].rank, 2)

    def test_daily_lines_are_ordered_by_date(self):
        session = self._open_session()
        self._make_order(
            session, [(self.unga, 5)], [(self.method_cash, 600.0)],
            order_date="2025-01-24 10:00:00",
        )
        self._make_order(
            session, [(self.unga, 1)], [(self.method_cash, 120.0)],
            order_date="2025-01-21 10:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()
        dates = [line.date.isoformat() for line in report.daily_line_ids]
        self.assertEqual(dates, sorted(dates))

    def test_grand_totals_reconcile_with_daily_lines(self):
        """US-RPT-03: grand totals must equal the sum of the daily rows."""
        session = self._open_session()
        self._make_order(
            session, [(self.unga, 2)], [(self.method_cash, 240.0)],
            order_date="2025-01-21 10:00:00",
        )
        self._make_order(
            session, [(self.milk, 4)], [(self.method_mpesa, 260.0)],
            order_date="2025-01-23 10:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()

        self.assertEqual(report.grand_total_sales, 500.0)
        self.assertEqual(report.grand_total_cash, 240.0)
        self.assertEqual(report.grand_total_mpesa, 260.0)
        self.assertEqual(
            report.grand_total_sales,
            sum(report.daily_line_ids.mapped("total_sales")),
        )

    def test_item_lines_carry_department_and_barcode(self):
        """US-RPT-04: items resolve to Department -> Category."""
        session = self._open_session()
        self._make_order(
            session, [(self.unga, 7)], [(self.method_cash, 840.0)],
            order_date="2025-01-22 10:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()

        item = report.item_line_ids
        self.assertEqual(len(item), 1)
        self.assertEqual(item.product_id, self.unga)
        self.assertEqual(item.barcode, "6001253001001")
        self.assertEqual(item.qty_sold, 7.0)
        self.assertEqual(item.total_sales, 840.0)
        self.assertEqual(item.categ_id, self.env.ref("retail_base.categ_flour_grains"))
        self.assertEqual(item.department_id, self.env.ref("retail_base.categ_dry_foods"))

    def test_orders_outside_range_are_excluded(self):
        session = self._open_session()
        self._make_order(
            session, [(self.unga, 1)], [(self.method_cash, 120.0)],
            order_date="2025-02-10 10:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()
        self.assertFalse(report.daily_line_ids)
        self.assertEqual(report.grand_total_sales, 0.0)

    def test_regenerating_replaces_previous_lines(self):
        session = self._open_session()
        self._make_order(
            session, [(self.unga, 1)], [(self.method_cash, 120.0)],
            order_date="2025-01-22 10:00:00",
        )
        report = self._new_report("2025-01-20", "2025-01-26")
        report.action_generate()
        first_count = len(report.daily_line_ids)
        report.action_generate()
        self.assertEqual(len(report.daily_line_ids), first_count)
