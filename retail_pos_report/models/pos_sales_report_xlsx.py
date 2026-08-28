"""XLSX export for the POS sales summary (US-RPT-02).

Written with xlsxwriter directly rather than through OCA report_xlsx:
xlsxwriter already ships with Odoo, so the export needs no module that is not
in Community Edition.
"""

import base64
import io

import xlsxwriter

from odoo import fields, models
from odoo.exceptions import UserError

class PosSalesReportXlsx(models.Model):
    _inherit = "pos.sales.report"

    xlsx_file = fields.Binary(string="Excel File", readonly=True, attachment=True)
    xlsx_filename = fields.Char(readonly=True)

    # Column layouts: (header, field, width, numeric)
    DAILY_COLUMNS = [
        ("Date", "date", 14, False),
        ("Total Sales", "total_sales", 16, True),
        ("MPESA", "mpesa_amount", 16, True),
        ("Cash", "cash_amount", 16, True),
        ("Other", "other_amount", 16, True),
        ("Rank", "rank", 8, False),
    ]
    ITEM_COLUMNS = [
        ("Dept", "department_id", 18, False),
        ("Category", "categ_id", 18, False),
        ("Product", "product_id", 34, False),
        ("Barcode", "barcode", 16, False),
        ("Qty Sold", "qty_sold", 12, True),
        ("Unit Price", "price_unit", 14, True),
        ("Total Sales", "total_sales", 16, True),
        ("Tax Ex", "amount_tax_excluded", 14, True),
        ("VAT", "amount_vat", 14, True),
    ]

    def action_export_xlsx(self):
        self.ensure_one()
        if self.state != "generated":
            raise UserError(
                self.env._("Generate the report before exporting it.")
            )
        self.write(
            {
                "xlsx_file": base64.b64encode(self._build_xlsx()),
                "xlsx_filename": "%s.xlsx" % self.name.replace("/", "-"),
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/pos.sales.report/%s/xlsx_file/%s?download=true"
            % (self.id, self.xlsx_filename),
            "target": "self",
        }

    def _build_xlsx(self):
        """Return the workbook bytes: one sheet per tab, each with a total row."""
        self.ensure_one()
        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {"in_memory": True})
        styles = self._xlsx_styles(workbook)
        self._write_daily_sheet(workbook, styles)
        self._write_item_sheet(workbook, styles)
        workbook.close()
        return stream.getvalue()

    def _xlsx_styles(self, workbook):
        return {
            "title": workbook.add_format({"bold": True, "font_size": 13}),
            "header": workbook.add_format(
                {"bold": True, "bg_color": "#DDDDDD", "border": 1}
            ),
            "text": workbook.add_format({"border": 1}),
            "money": workbook.add_format({"border": 1, "num_format": "#,##0.00"}),
            "qty": workbook.add_format({"border": 1, "num_format": "#,##0.##"}),
            "date": workbook.add_format({"border": 1, "num_format": "yyyy-mm-dd"}),
            "total_text": workbook.add_format(
                {"bold": True, "border": 1, "bg_color": "#F2F2F2"}
            ),
            "total_money": workbook.add_format(
                {
                    "bold": True,
                    "border": 1,
                    "bg_color": "#F2F2F2",
                    "num_format": "#,##0.00",
                }
            ),
        }

    def _write_sheet_title(self, sheet, styles, title, columns):
        sheet.write(0, 0, title, styles["title"])
        sheet.write(
            1,
            0,
            "%s  |  %s to %s"
            % (self.name, self.date_from or "", self.date_to or ""),
        )
        for index, (header, _field, width, _numeric) in enumerate(columns):
            sheet.set_column(index, index, width)
            sheet.write(3, index, header, styles["header"])
        return 4

    def _write_daily_sheet(self, workbook, styles):
        sheet = workbook.add_worksheet("Daily Summary")
        row = self._write_sheet_title(sheet, styles, "Daily Summary", self.DAILY_COLUMNS)
        for line in self.daily_line_ids:
            if line.date:
                sheet.write_datetime(row, 0, line.date, styles["date"])
            else:
                sheet.write(row, 0, "", styles["text"])
            sheet.write_number(row, 1, line.total_sales, styles["money"])
            sheet.write_number(row, 2, line.mpesa_amount, styles["money"])
            sheet.write_number(row, 3, line.cash_amount, styles["money"])
            sheet.write_number(row, 4, line.other_amount, styles["money"])
            sheet.write_number(row, 5, line.rank, styles["text"])
            row += 1

        sheet.write(row, 0, "Grand Total", styles["total_text"])
        sheet.write_number(row, 1, self.grand_total_sales, styles["total_money"])
        sheet.write_number(row, 2, self.grand_total_mpesa, styles["total_money"])
        sheet.write_number(row, 3, self.grand_total_cash, styles["total_money"])
        sheet.write_number(row, 4, self.grand_total_other, styles["total_money"])
        sheet.write(row, 5, "", styles["total_text"])

    def _write_item_sheet(self, workbook, styles):
        sheet = workbook.add_worksheet("Sales by Item")
        row = self._write_sheet_title(sheet, styles, "Sales by Item", self.ITEM_COLUMNS)
        totals = {"qty_sold": 0.0, "total_sales": 0.0, "amount_tax_excluded": 0.0, "amount_vat": 0.0}
        for line in self.item_line_ids:
            sheet.write(row, 0, line.department_id.name or "", styles["text"])
            sheet.write(row, 1, line.categ_id.name or "", styles["text"])
            sheet.write(row, 2, line.product_id.display_name or "", styles["text"])
            sheet.write(row, 3, line.barcode or "", styles["text"])
            sheet.write_number(row, 4, line.qty_sold, styles["qty"])
            sheet.write_number(row, 5, line.price_unit, styles["money"])
            sheet.write_number(row, 6, line.total_sales, styles["money"])
            sheet.write_number(row, 7, line.amount_tax_excluded, styles["money"])
            sheet.write_number(row, 8, line.amount_vat, styles["money"])
            for key in totals:
                totals[key] += line[key]
            row += 1

        sheet.write(row, 0, "Grand Total", styles["total_text"])
        for column in (1, 2, 3):
            sheet.write(row, column, "", styles["total_text"])
        sheet.write_number(row, 4, totals["qty_sold"], styles["total_money"])
        sheet.write(row, 5, "", styles["total_text"])
        sheet.write_number(row, 6, totals["total_sales"], styles["total_money"])
        sheet.write_number(row, 7, totals["amount_tax_excluded"], styles["total_money"])
        sheet.write_number(row, 8, totals["amount_vat"], styles["total_money"])
