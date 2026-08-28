# Tano Retail — Odoo 18 CE

Custom Odoo 18 **Community** modules for Kenyan supermarket retail operations:
point of sale, stock requisition between the central warehouse and branches,
purchase requests with threshold approval, POS sales reporting, M-PESA at the
till, and Kenyan fiscal classification.

These are standard Odoo addons. They contain no machine-specific configuration
and install on any Odoo 18 CE instance. Nothing depends on Odoo Enterprise.

---

## Installation

1. Add this repository to `addons_path` in your `odoo.conf`. The modules sit
   at the repository root, so point at the repository itself:

   ```ini
   addons_path = /opt/odoo/addons,/srv/Retail
   ```

2. Restart Odoo and update the apps list.

3. Install what you need; dependencies resolve automatically:

   ```bash
   odoo-bin -d <database> -i retail_base,retail_stock_requisition
   ```

`config/odoo.conf.example` is a starting point for a development instance. It
is a convenience, not a deployment artefact.

---

## Modules

```
retail_base                       KES, branches, six roles, departments, loyalty
 ├── retail_stock_requisition     six-state branch replenishment
 ├── retail_purchase_request      purchase requests + threshold approval
 ├── retail_pos_report            daily and per-item sales summary
 ├── retail_pos                   out-of-stock guard, return window
 ├── retail_fiscal_ke             Kenyan VAT classification, ESD printing
 └── retail_mpesa_base            Safaricom Daraja: config, ledger, callbacks
      └── retail_mpesa_pos        M-PESA payment method at the till
```

| Module | Tests | What it does |
|---|---:|---|
| `retail_base` | 17 | Six security groups, branch warehouses, user branch scoping, department hierarchy, Tano Points loyalty, payment reporting buckets |
| `retail_stock_requisition` | 49 | Six-state approval chain creating a real internal transfer |
| `retail_purchase_request` | 29 | Request lifecycle plus data-driven approval thresholds |
| `retail_pos_report` | 20 | Daily and per-item sales with M-PESA/cash/other split |
| `retail_mpesa_base` | 36 | Daraja OAuth, STK push, C2B, idempotent callbacks |
| `retail_pos` | 17 | Out-of-stock guard, configurable return window |
| `retail_mpesa_pos` | 18 | STK push and manual code capture at the till |
| `retail_fiscal_ke` | 35 | PTU classification, HS codes, fiscal printer and audit log |

### What Odoo 18 CE already provides

Roughly half the original user stories need **configuration, not code**: POS
sessions and cash control, closing variance, split payments, loyalty points
(`loyalty` and `pos_loyalty` are Community since v17), refunds, internal
transfers, RFQs, and goods receipt with backorders. Those are deliberately not
reimplemented here.

### Notable behaviours

- **Branch scoping.** `res.users.retail_warehouse_ids` limits which branches a
  user may transact against. An empty assignment means unrestricted, so head
  office is not locked out.
- **Approved, not requested, quantities.** A finance-approved requisition
  transfers what the supply chain officer approved; lines approved at zero are
  omitted.
- **Approval thresholds are data.** `retail.approval.threshold` maps an amount
  band to a group, so changing who signs off at what value is a configuration
  row. Raising an order total past a threshold reopens approval.
- **Reports aggregate in SQL.** A week across five tills is six figures of
  order lines. Days bucket in the user's timezone, so a till trading past
  midnight stays one trading day and cash reconciles against the till count.
- **M-PESA has two capture routes.** STK push, and manual code entry for a
  customer who paid the till from their own handset. The second is not a
  fallback — it is how most Kenyan till payments happen. Cancelling capture
  adds no payment line, because an M-PESA line without a code cannot be
  reconciled against Safaricom settlement.
- **Callbacks are idempotent and IP-allowlisted.** Daraja retries; a replay
  must never credit an order twice.
- **Secrets are not stored.** `mpesa.config` holds only the *names* of
  `ir.config_parameter` keys, so a database dump carries no live credentials.
- **Mixed VAT basket.** Products classify as taxable, exempt or zero rated
  from their single tax. A blanket 16% is wrong for a Kenyan basket: maize
  flour and milk are not standard rated.

---

## Running the tests

Every acceptance case from the requirements document is a named test, so
`TC-STK-01` maps to `test_tc_stk_01_full_approval_flow`.

```bash
odoo-bin -d <test-database> \
  -i retail_base,retail_stock_requisition,retail_purchase_request,\
retail_pos_report,retail_mpesa_base,retail_pos,retail_mpesa_pos,retail_fiscal_ke \
  --test-enable --stop-after-init \
  --log-handler odoo.tests.common:ERROR
```

`--log-handler odoo.tests.common:ERROR` suppresses a broken RUNBOT-level log
call in Odoo 18.0 (`odoo/fields.py` `__str__` reads `Field.name` before it is
set). It is cosmetic, but without it a multi-module run emits over a million
lines of logging-error stacks.

`python scripts/preflight.py` runs fast static checks — manifest sanity, XML
well-formedness, Python syntax, missing data files — in seconds rather than
after a multi-minute install.

External systems are **always mocked**. No test reaches Safaricom or opens a
socket to a fiscal device.

### Known verification gaps

- **OWL front-end code is not covered by browser tours.** The out-of-stock
  guard and the M-PESA payment popup have their server side fully tested, but
  the JavaScript itself is unexercised. Chrome is present, so tours are
  possible; they have not been written.
- **`retail_fiscal_ke` failure logging is asserted by call, not by row.** The
  audit row is written on an independent cursor so it survives the rollback
  the raise causes. That cursor cannot see `TransactionCase` fixtures, which
  are never committed, so the test asserts the call and its values rather than
  the persisted row.

---

## Open items before production

1. **The Novitus wire format is not ported.** `_build_fiscal_payload()` emits
   a documented XML envelope with the correct data, but it is not
   byte-compatible with the device. Pin it against real hardware at the
   `fiscal_printer._send` seam.
2. **KRA eTIMS.** Novitus ESD is TIMS-era hardware. Kenya moved to eTIMS in
   2024 and CE has no connector. Whether an ESD device still satisfies KRA is
   a question for the client's tax advisor.
3. **Daraja production credentials and a public HTTPS callback URL**, which
   Safaricom must whitelist. Long lead time.
4. **`stk_push` writes its pending row on the caller's cursor**, after
   Safaricom has already prompted the customer. If that request rolls back,
   the customer can pay with no pending row for the callback to match. The
   out-of-band pattern used in `retail_fiscal_ke` would remove the risk.
5. **The source document's VAT figures do not reconcile** and US-PRQ-03
   contradicts its own acceptance criteria. Thresholds are seeded from the
   acceptance criteria, and the discrepancy is noted in
   `retail_purchase_request/data/approval_threshold_data.xml`.

---

## Requirements

- Odoo 18.0 Community Edition
- Python 3.12
- PostgreSQL 12 or later

`requirements.txt` lists the extra Python dependencies beyond Odoo's own.
