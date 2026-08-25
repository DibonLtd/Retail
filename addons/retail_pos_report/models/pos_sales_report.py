from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

# POS orders in these states represent completed sales.
SOLD_STATES = ("done", "invoiced")


class PosSalesReport(models.Model):
    _name = "pos.sales.report"
    _description = "POS Sales Summary Report"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True, default="New"
    )
    state = fields.Selection(
        selection=[("draft", "Draft"), ("generated", "Generated")],
        default="draft",
        required=True,
        copy=False,
    )
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    config_ids = fields.Many2many(
        comodel_name="pos.config",
        string="Points of Sale",
        help="Leave empty to include every till.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company", default=lambda self: self.env.company, required=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    daily_line_ids = fields.One2many(
        comodel_name="pos.sales.daily.line",
        inverse_name="report_id",
        string="Daily Summary",
        readonly=True,
    )
    item_line_ids = fields.One2many(
        comodel_name="pos.sales.item.line",
        inverse_name="report_id",
        string="Sales by Item",
        readonly=True,
    )

    grand_total_sales = fields.Monetary(
        compute="_compute_grand_totals", currency_field="currency_id", store=True
    )
    grand_total_mpesa = fields.Monetary(
        compute="_compute_grand_totals", currency_field="currency_id", store=True
    )
    grand_total_cash = fields.Monetary(
        compute="_compute_grand_totals", currency_field="currency_id", store=True
    )
    grand_total_other = fields.Monetary(
        compute="_compute_grand_totals", currency_field="currency_id", store=True
    )

    # ------------------------------------------------------------------
    # Computes and constraints
    # ------------------------------------------------------------------

    @api.depends(
        "daily_line_ids.total_sales",
        "daily_line_ids.mpesa_amount",
        "daily_line_ids.cash_amount",
        "daily_line_ids.other_amount",
    )
    def _compute_grand_totals(self):
        for report in self:
            lines = report.daily_line_ids
            report.grand_total_sales = sum(lines.mapped("total_sales"))
            report.grand_total_mpesa = sum(lines.mapped("mpesa_amount"))
            report.grand_total_cash = sum(lines.mapped("cash_amount"))
            report.grand_total_other = sum(lines.mapped("other_amount"))

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for report in self:
            if report.date_from and report.date_to and report.date_from > report.date_to:
                raise ValidationError(
                    self.env._("The start date must not be after the end date.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("pos.sales.report") or "New"
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _order_domain_sql(self):
        """Return an SQL WHERE fragment and its parameters for the order scope.

        Aggregation is done in SQL rather than the ORM: a week across five
        tills is six figures of order lines, which the ORM cannot walk at
        chain volume.
        """
        self.ensure_one()
        clauses = [
            "o.state IN %s",
            "o.company_id = %s",
            "(o.date_order AT TIME ZONE 'UTC' AT TIME ZONE %s)::date BETWEEN %s AND %s",
        ]
        params = [
            SOLD_STATES,
            self.company_id.id,
            self._report_timezone(),
            self.date_from,
            self.date_to,
        ]
        if self.config_ids:
            clauses.append("o.config_id IN %s")
            params.append(tuple(self.config_ids.ids))
        return " AND ".join(clauses), params

    def _report_timezone(self):
        """Days are bucketed in the user's timezone, not UTC.

        A till open past midnight would otherwise split one trading day
        across two report rows.
        """
        return self.env.user.tz or "UTC"

    def action_generate(self):
        for report in self:
            report.daily_line_ids.unlink()
            report.item_line_ids.unlink()
            report._generate_daily_lines()
            report._generate_item_lines()
            report.state = "generated"
        return True

    def _generate_daily_lines(self):
        self.ensure_one()
        where, params = self._order_domain_sql()
        tz = self._report_timezone()

        # Sales per day.
        self.env.cr.execute(
            f"""
            SELECT (o.date_order AT TIME ZONE 'UTC' AT TIME ZONE %s)::date AS day,
                   SUM(o.amount_total) AS total
              FROM pos_order o
             WHERE {where}
             GROUP BY day
            """,
            [tz] + params,
        )
        totals = {row[0]: row[1] or 0.0 for row in self.env.cr.fetchall()}

        # Payments per day, split by reporting bucket.
        self.env.cr.execute(
            f"""
            SELECT (o.date_order AT TIME ZONE 'UTC' AT TIME ZONE %s)::date AS day,
                   COALESCE(m.retail_payment_bucket, 'other') AS bucket,
                   SUM(p.amount) AS total
              FROM pos_payment p
              JOIN pos_order o ON p.pos_order_id = o.id
              JOIN pos_payment_method m ON p.payment_method_id = m.id
             WHERE {where}
             GROUP BY day, bucket
            """,
            [tz] + params,
        )
        buckets = {}
        for day, bucket, amount in self.env.cr.fetchall():
            buckets.setdefault(day, {})[bucket] = amount or 0.0

        rows = []
        for day, total in totals.items():
            by_bucket = buckets.get(day, {})
            rows.append(
                {
                    "report_id": self.id,
                    "date": day,
                    "total_sales": total,
                    "mpesa_amount": by_bucket.get("mpesa", 0.0),
                    "cash_amount": by_bucket.get("cash", 0.0),
                    "other_amount": by_bucket.get("other", 0.0),
                }
            )

        # Rank 1 is the highest-selling day.
        rows.sort(key=lambda row: row["total_sales"], reverse=True)
        for position, row in enumerate(rows, start=1):
            row["rank"] = position

        rows.sort(key=lambda row: row["date"])
        self.env["pos.sales.daily.line"].create(rows)

    def _generate_item_lines(self):
        self.ensure_one()
        where, params = self._order_domain_sql()
        self.env.cr.execute(
            f"""
            SELECT l.product_id,
                   SUM(l.qty) AS qty,
                   SUM(l.price_subtotal_incl) AS total_incl,
                   SUM(l.price_subtotal) AS total_excl
              FROM pos_order_line l
              JOIN pos_order o ON l.order_id = o.id
             WHERE {where}
             GROUP BY l.product_id
            """,
            params,
        )
        raw = self.env.cr.fetchall()
        if not raw:
            return

        products = self.env["product.product"].browse([row[0] for row in raw])
        by_id = {product.id: product for product in products}

        rows = []
        for product_id, qty, total_incl, total_excl in raw:
            product = by_id.get(product_id)
            if not product:
                continue
            category = product.categ_id
            rows.append(
                {
                    "report_id": self.id,
                    "product_id": product_id,
                    "categ_id": category.id,
                    "department_id": self._root_category(category).id,
                    "barcode": product.barcode or "",
                    "qty_sold": qty or 0.0,
                    "price_unit": (total_incl / qty) if qty else 0.0,
                    "total_sales": total_incl or 0.0,
                    "amount_tax_excluded": total_excl or 0.0,
                    "amount_vat": (total_incl or 0.0) - (total_excl or 0.0),
                }
            )
        self.env["pos.sales.item.line"].create(rows)

    @staticmethod
    def _root_category(category):
        """Return the top-level ancestor of ``category``, which is the department."""
        current = category
        while current.parent_id:
            current = current.parent_id
        return current


class PosSalesDailyLine(models.Model):
    _name = "pos.sales.daily.line"
    _description = "POS Sales Daily Summary Line"
    _order = "date"

    report_id = fields.Many2one(
        comodel_name="pos.sales.report", required=True, ondelete="cascade", index=True
    )
    currency_id = fields.Many2one(related="report_id.currency_id", readonly=True)
    date = fields.Date(required=True)
    total_sales = fields.Monetary(currency_field="currency_id")
    mpesa_amount = fields.Monetary(currency_field="currency_id", string="M-PESA")
    cash_amount = fields.Monetary(currency_field="currency_id", string="Cash")
    other_amount = fields.Monetary(currency_field="currency_id", string="Other")
    rank = fields.Integer(help="1 is the highest-selling day in the range.")


class PosSalesItemLine(models.Model):
    _name = "pos.sales.item.line"
    _description = "POS Sales Item Line"
    _order = "department_id, categ_id, total_sales desc"

    report_id = fields.Many2one(
        comodel_name="pos.sales.report", required=True, ondelete="cascade", index=True
    )
    currency_id = fields.Many2one(related="report_id.currency_id", readonly=True)
    department_id = fields.Many2one(
        comodel_name="product.category",
        string="Department",
        help="Top-level product category.",
    )
    categ_id = fields.Many2one(comodel_name="product.category", string="Category")
    product_id = fields.Many2one(comodel_name="product.product", string="Product")
    barcode = fields.Char()
    qty_sold = fields.Float(digits="Product Unit of Measure")
    price_unit = fields.Monetary(currency_field="currency_id")
    total_sales = fields.Monetary(currency_field="currency_id")
    amount_tax_excluded = fields.Monetary(
        currency_field="currency_id", string="Tax Excl."
    )
    amount_vat = fields.Monetary(currency_field="currency_id", string="VAT")
