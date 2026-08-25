# Tano Supermarket — Odoo 18 CE Retail Build

**Design specification**
Date: 2026-08-25
Status: Draft for review
Target: Odoo 18.0 Community Edition

---

## 1. Context and scope

Tano Supermarket is a mid-size Kenyan chain with four branches (Westgate, Thika Road
Mall, Junction in Nairobi; City Mall in Mombasa) plus a central warehouse and head
office. This document specifies a production Odoo 18 CE build covering four
operational areas: point-of-sale, stock requisition between the warehouse and
branches, purchase requests to external suppliers, and POS sales reporting.

The source requirements are the user-story document supplied by the client, which
describes an adaptation of the Trinity-Energy Odoo build. That build is Odoo 17 and
is welded to a fuel/petroleum domain — `retail_stock_requisition` there depends on
`oo_fuel_management_system`. This build is therefore **retail-native and written
fresh against Odoo 18 CE**, using the existing modules as logic reference only.

### 1.1 Currency and tax context

- Currency: Kenya Shilling (KES)
- VAT: administered per-product via fiscal classification (see §4.2), not a blanket rate
- Payment methods: Cash, Lipa na M-PESA (Till 174379), bank card
- Fiscal device: Novitus ESD, driven over TCP socket

### 1.2 Out of scope

- Payroll and HR (covered by separate `hr_ke` modules)
- E-commerce / website ordering
- Fleet and delivery routing
- Data migration from a legacy system (fresh database assumed)

---

## 2. What Odoo 18 CE already provides

The single most important design decision is what **not** to build. Roughly half the
supplied user stories are satisfied by standard Odoo 18 CE and require configuration,
not code. Writing custom code for these would create maintenance burden and upgrade
risk for no functional gain.

| Story | Requirement | Standard Odoo 18 CE mechanism |
|---|---|---|
| US-POS-01 | Open session with cash float | `pos.session` cash control, `cash_register_balance_start` |
| US-POS-02 | Barcode scanning | Standard POS barcode handler |
| US-POS-03 | Cash payment, change, drawer | Standard payment screen |
| US-POS-05 | Split payment across methods | Multiple `pos.payment` lines per order |
| US-POS-06 | Loyalty points earn/redeem | `loyalty.program`, `loyalty.card`, `pos_loyalty` (CE since v17) |
| US-POS-07 | Return / refund | Standard POS refund flow |
| US-POS-08 | Close session, variance | Closing control, `cash_real_difference` |
| US-STK-03 | Internal transfer creation | `stock.picking` type `internal` |
| US-STK-04 | Receive goods at branch | Standard picking validation |
| US-PRQ-02 | RFQ to suppliers | Standard `purchase.order` in draft |
| US-PRQ-04 | GRN, short delivery, backorder | Standard receipt picking + backorder wizard |

**Configuration required** (delivered as data in `retail_base`): one warehouse per
branch, POS configs per till, loyalty program at 1 point per KES 10 earned and
KES 0.10 per point redeemed, payment methods, and the branch/product master data.

### 2.1 Gaps requiring custom code

| # | Gap | Module | Why CE cannot do it |
|---|---|---|---|
| 1 | Six-state requisition approval chain | `retail_stock_requisition` | No such workflow exists in CE |
| 2 | M-PESA / Safaricom Daraja | `retail_mpesa_base`, `retail_mpesa_pos` | No CE integration |
| 3 | Block zero-quantity items at the till | `retail_pos` | Requires OWL patch |
| 4 | Threshold-based multi-level PO approval | `retail_purchase_request` | CE has no `approvals` module — Enterprise only |
| 5 | Daily/item sales summary with ranking + xlsx | `retail_pos_report` | Bespoke report structure |
| 6 | Kenyan fiscal classification and ESD printing | `retail_fiscal_ke` | Port of existing v17 module |
| 7 | Company, branches, roles, KE master data | `retail_base` | Foundation data |

---

## 3. Module architecture

Layered small modules, each independently installable and testable. No module
depends on a sibling except through the declared graph below.

```
retail_base                        company, KES, branches, 6 security groups, master data
  |
  +-- retail_fiscal_ke             product fiscal class, account.tax PTU, ESD printer, fiscal log
  |     |
  |     +-- retail_pos             zero-qty block, receipt layout, return window
  |           |
  |           +-- retail_mpesa_pos POS payment method, STK push screen
  |                 (also depends on retail_mpesa_base)
  |
  +-- retail_mpesa_base            Daraja config, mpesa.transaction, callback controllers
  +-- retail_stock_requisition     six-state requisition + internal transfer
  +-- retail_purchase_request      purchase request + threshold approval
  +-- retail_pos_report            daily/item sales summary + xlsx export
```

### 3.1 Repository layout

```
Retail/
|-- addons/
|   |-- retail_base/
|   |-- retail_fiscal_ke/
|   |-- retail_pos/
|   |-- retail_stock_requisition/
|   |-- retail_mpesa_base/
|   |-- retail_mpesa_pos/
|   |-- retail_purchase_request/
|   `-- retail_pos_report/
|-- config/odoo.conf
|-- docker-compose.yml
|-- requirements.txt
|-- docs/superpowers/specs/
|-- .github/workflows/ci.yml
`-- README.md
```

### 3.2 Third-party dependencies

| Dependency | Purpose | Source |
|---|---|---|
| `l10n_ke` | Kenyan chart of accounts | Odoo 18 CE core |
| `report_xlsx` | XLSX report engine | OCA `reporting-engine` 18.0 |
| `xlsxwriter` | XLSX writing | pip |
| `xmltodict` | ESD protocol parsing | pip |
| `pyqrcode`, `pypng` | Fiscal invoice QR codes | pip |

Mature OCA plumbing is preferred over reimplementation. "Built fresh" means
retail-native and decoupled from the Trinity fuel domain, not refusal of
well-maintained community infrastructure.

---

## 4. Data models

### 4.1 `retail_base`

Adds no business models. Delivers:

- **Security groups** under a "Tano Retail" category. Reuses
  `point_of_sale.group_pos_user` (cashier) and `point_of_sale.group_pos_manager`
  (store manager). Adds `group_supply_chain_officer`, `group_finance_officer`,
  `group_procurement_manager`, `group_purchase_cfo`.
- **`res.users.retail_warehouse_ids`** — many2many to `stock.warehouse`. Defines
  which branches a user may transact against. This is the mechanism behind TC-STK-02.
- **Master data**: company, KES currency, four branch warehouses plus Central
  Warehouse, POS configs per till, product categories mirroring the department to
  category hierarchy the sales report groups by, and the loyalty program.

Branch modelling uses Odoo's native multi-warehouse support. No custom "station"
entity is introduced.

### 4.2 `retail_fiscal_ke` (port of `custom_esd_pos_account_novitus` 17.0.0.3)

Existing model surface, carried forward:

| Model | Key fields |
|---|---|
| `product.template` | `factor_type` (PTU classification letter), `hscode_index` |
| `account.tax` | `fiscal_ptu_value`, `factor_type` |
| `fiscal.printer` | Device address, port, connection state |
| `account.fiscal.log` | Per-document fiscal transmission audit trail |
| `account.move` | Fiscal signature fields, QR payload |
| `pos.order` | Fiscal receipt linkage |

This module is the authority on VAT treatment. Products carry a PTU letter mapping
them to exempt, zero-rated, 8% or standard 16% treatment, which is the correct model
for a Kenyan supermarket basket — maize flour and milk are not standard-rated.

> **Note on the source document.** The VAT figures in the supplied acceptance tests
> do not reconcile arithmetically. TC-POS-01 shows a 480.00 subtotal with 65.93 VAT;
> 16% exclusive gives 76.80 and 16% inclusive gives 66.21. TC-POS-02 has the same
> problem (1,165.00 against 160.69, where exclusive gives 186.40). These expected
> values will be recomputed from the fiscal classification of each product during
> implementation, and every changed figure listed explicitly rather than silently
> corrected.

### 4.3 `retail_stock_requisition`

**`retail.stock.requisition`** — inherits `mail.thread`, `mail.activity.mixin`.

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Sequence `RSR/%(year)s/#####` |
| `state` | Selection | `draft`, `submitted`, `sc_validated`, `finance_approved`, `done`, `rejected`, `cancelled` |
| `requestor_id` | Many2one res.users | Default current user |
| `source_location_id` | Many2one stock.location | Central Warehouse stock |
| `dest_warehouse_id` | Many2one stock.warehouse | Validated against the requestor's allowed warehouses |
| `date_required` | Date | Required-by date |
| `line_ids` | One2many | Requisition lines |
| `picking_ids` | One2many stock.picking | Populated by `_create_internal_picking()` |
| `rejection_reason` | Text | Stamped by reject wizard |
| `rejected_by_id` | Many2one res.users | Stamped by reject wizard |
| `sc_validated_by_id` / `sc_validated_date` | Many2one / Datetime | Audit stamp |
| `finance_approved_by_id` / `finance_approved_date` | Many2one / Datetime | Audit stamp |

**`retail.stock.requisition.line`**

| Field | Type | Notes |
|---|---|---|
| `product_id`, `product_uom_id` | Many2one | |
| `qty_requested` | Float | Entered by requestor |
| `qty_approved` | Float | Adjustable by supply chain officer |
| `qty_received` | Float | Computed from validated move quantities |
| `qty_available_source` | Float | Computed on-hand at source, shown for informed approval |

**`retail.requisition.reject.wizard`** — transient, one required `reason` field.

#### State machine

```
[draft] --submit--> [submitted] --sc_validate--> [sc_validated] --finance_approve--> [finance_approved]
   |                     |                            |                                     |
 cancel                cancel                      reject                          picking validated
   |                     |                            |                                     |
[cancelled]         [cancelled]                  [rejected]                              [done]
                                                      |
                                              reset_to_draft
                                                      |
                                                   [draft]
```

#### Method contracts

| Method | Behaviour |
|---|---|
| `action_submit()` | Raises `UserError` if `dest_warehouse_id` is not in the requestor's `retail_warehouse_ids`. Sets `submitted`, notifies supply chain group. |
| `action_sc_validate()` | Sets `sc_validated`, stamps approver, notifies finance group. |
| `action_finance_approve()` | Calls `_create_internal_picking()`, sets `finance_approved`, notifies requestor. |
| `_create_internal_picking()` | Creates one internal `stock.picking` from source to destination, one move per line at `qty_approved`. |
| `action_reject()` | Opens reject wizard. On confirm sets `rejected`, stamps reason and rejector, notifies requestor. |
| `action_cancel()` | Permitted only from `draft` or `submitted`. Raises `UserError` otherwise. No notification. |
| `action_reset_to_draft()` | Permitted from `rejected`. Clears rejection stamps. |
| `_action_set_done()` | Called from a `stock.picking.button_validate` override when all linked pickings are done. |

### 4.4 `retail_mpesa_base` and `retail_mpesa_pos`

**`mpesa.config`** — per company: shortcode, passkey, consumer key, consumer secret,
environment (`sandbox` / `production`), callback base URL. Credentials resolve from
`ir.config_parameter` seeded by environment variable; never committed to git.

**`mpesa.transaction`** — `receipt_number` (Safaricom `MpesaReceiptNumber`),
`checkout_request_id`, `merchant_request_id`, `amount`, `phone`, `state`
(`pending` / `success` / `failed` / `timeout`), `pos_order_id`, `account_move_id`,
`raw_response` (JSON text, retained for dispute resolution).

**Controllers** — `/mpesa/callback/stk`, `/mpesa/callback/c2b/validation`,
`/mpesa/callback/c2b/confirmation`. All `auth='public'`, `csrf=False`, guarded by a
Safaricom IP allowlist and idempotent on `checkout_request_id` so a replayed callback
cannot double-credit an order.

**POS integration** — a payment method of type `mpesa`. The payment screen offers two
paths, and both are required:

1. **STK push** — the cashier enters the customer phone number, Odoo pushes, the
   screen polls `checkout_request_id` until the callback resolves, and the receipt
   number auto-fills.
2. **Manual reference** — the customer pays Till 174379 directly from their own
   handset and reads out the confirmation code. This path never triggers an STK push,
   and is how most Kenyan till payments actually happen. Omitting it would make the
   till unusable.

### 4.5 `retail_purchase_request`

**Decision: own models rather than OCA `purchase_request`.** OCA's module was
evaluated as a base. It was rejected because its own approval model would have to be
bypassed to accommodate the KES threshold bands, leaving two competing approval
mechanisms in one module. The request lifecycle here is small enough that inheriting
that conflict costs more than writing it. This differs from the `report_xlsx`
decision in §3.2, where the OCA module is used as-is because nothing about it
conflicts with the requirements.

**`retail.purchase.request`** and `.line` — request lifecycle from raise through
approval to RFQ creation.

**`retail.approval.threshold`** — `company_id`, `amount_from`, `amount_to`,
`group_id`, `sequence`. Approval requirements are **data, not constants**.

> **Note on the source document.** US-PRQ-03 is self-contradictory: the story states
> that orders above KES 500,000 require CFO approval, while its acceptance criteria
> state that the procurement manager approves below KES 1M and the CFO is required
> above KES 1M. Data-driven thresholds make this a configuration row rather than a
> code change. Seeded values follow the acceptance criteria; the client should confirm
> the intended bands before go-live.

`purchase.order.button_confirm()` is overridden to block confirmation until every
threshold applicable to `amount_total` has a matching approval record.

### 4.6 `retail_pos_report`

**`pos.sales.report`** — `name` (sequence `PSR/%(year)s/####`), `date_from`,
`date_to`, `config_ids`, `state`, `daily_line_ids`, `item_line_ids`,
`grand_total_sales`, `grand_total_mpesa`, `grand_total_cash`, `grand_total_other`.

**`pos.sales.daily.line`** — `date`, `total_sales`, `mpesa_amount`, `cash_amount`,
`other_amount`, `rank` (1 = highest-selling day).

**`pos.sales.item.line`** — `department_id` (top-level product category),
`categ_id`, `product_id`, `barcode`, `qty_sold`, `price_unit`, `total_sales`,
`amount_tax_excluded`, `amount_vat`.

`action_generate()` aggregates `pos.order` in state `done` or `invoiced` across the
date range. **Implemented in raw SQL, not ORM loops.** A week across five tills is six
figures of order lines; the ORM approach used in the v17 reference will not survive
chain volume.

XLSX export via `report_xlsx`: two sheets (Daily Summary, Sales by Item), each with a
grand-total row.

---

## 5. Odoo 17 to 18 upgrade plan

Two modules are ports rather than new work: `custom_esd_pos_account_novitus` becomes
`retail_fiscal_ke`, and the reusable parts of `custom_pos` become `retail_pos`.

The Python (~2,400 LOC in the fiscal module) ports routinely. **The JavaScript is
where the risk sits**: seven files patch `models.js`, `PaymentScreen.js` and
`TicketScreen.js`, which are exactly the POS internals Odoo rewrote for 18.

### 5.1 Known breaking changes

| Change | Impact |
|---|---|
| `web.assets_qweb` bundle removed | Manifest asset declarations must move to `point_of_sale._assets_pos` |
| POS frontend rewritten in 18 | `models.js` patches must be rewritten against the new relational model registry |
| POS data loading changed | `pos.session` loader params replaced by per-model `_load_pos_data_fields` / `_load_pos_data_models` |
| OWL component API changes | PaymentScreen / TicketScreen patch points moved |
| `name_get()` removed | Replace with `_compute_display_name` |
| `<tree>` renamed `<list>` | All list views must be updated |

### 5.2 Method

Fresh database, so no OpenUpgrade data migration scripts. Each module is ported,
installed against a clean Odoo 18 instance, and verified by its test suite before the
next module in the dependency graph is started. A port is not complete until its tests
pass on 18.

---

## 6. Security model

| Persona | Group | Capability |
|---|---|---|
| Agnes Wanjiku, cashier | `point_of_sale.group_pos_user` | Operate assigned tills; no back office |
| David Kamau, store manager | `point_of_sale.group_pos_manager` | Sessions, refunds, requisitions, reports for own branches |
| Joseph Mwangi, supply chain | `group_supply_chain_officer` | Validate requisitions, adjust approved quantities |
| Margaret Otieno, finance | `group_finance_officer` | Approve requisitions, view all sales reports |
| Lydiah Muthoni, procurement | `group_procurement_manager` | Approve purchase requests, create RFQs |
| Susan Achieng, CFO | `group_purchase_cfo` | Top-tier PO approval |

### 6.1 Record rules

- Requisitions: the requestor sees their own records; managers see records for
  warehouses in their `retail_warehouse_ids`; supply chain and finance see all.
- Sales reports: manager level and above; managers restricted to their own branches.
- M-PESA transactions: read-only for POS users, full access for finance.

---

## 7. Testing strategy

Every `TC-*` case in the source document becomes a named automated test, so the
acceptance table traces directly to executable code.

| Test case | Test method | Type |
|---|---|---|
| TC-POS-01 | `test_tc_pos_01_cash_purchase_walk_in` | TransactionCase |
| TC-POS-02 | `test_tc_pos_02_mpesa_loyalty_customer` | TransactionCase |
| TC-POS-03 | `test_tc_pos_03_blocked_zero_qty` | HttpCase (POS tour) |
| TC-POS-04 | `test_tc_pos_04_split_payment` | HttpCase (POS tour) |
| TC-POS-05 | `test_tc_pos_05_session_close_variance` | TransactionCase |
| TC-STK-01 | `test_tc_stk_01_full_approval_flow` | TransactionCase |
| TC-STK-02 | `test_tc_stk_02_unauthorised_station_blocked` | TransactionCase |
| TC-STK-03 | `test_tc_stk_03_rejection_with_resubmission` | TransactionCase |
| TC-RPT-01 | `test_tc_rpt_01_weekly_sales_report` | TransactionCase |

### 7.1 External systems in tests

The Daraja API and the Novitus fiscal printer socket are **mocked without exception**.
No test may reach a live Safaricom endpoint or a physical device. Callback handling is
tested by posting recorded Safaricom payloads to the controller, including a replayed
duplicate to prove idempotency.

### 7.2 CI

GitHub Actions with a Postgres service and the `odoo:18.0` image, installing all eight
modules with `--test-enable --stop-after-init`.

---

## 8. Deployment

Matches the existing house convention (`~/Documents/GitHub/odoo/local-compose.yml`):
`odoo:18.0` image, `config/odoo.conf`, addons mounted at
`/mnt/extra-addons/custom-addons`, Postgres on the host.

Production additions:

- **TLS reverse proxy, mandatory.** Safaricom Daraja posts callbacks to a public HTTPS
  endpoint, and the URL must be registered and reachable. Without it, STK push cannot
  confirm.
- `workers > 0` and `proxy_mode = True` when running behind the proxy.
- Scheduled database and filestore backups.
- Secrets (Daraja keys, printer addresses) supplied via environment and stored in
  `ir.config_parameter`. Never committed.

---

## 9. Open risks and decisions

| # | Risk | Impact | Owner |
|---|---|---|---|
| 1 | **TIMS vs eTIMS.** Novitus ESD is TIMS-era hardware. Kenya moved to eTIMS (software OSCU/VSCU) in 2024 and KRA has been retiring the ESD path. Whether an ESD printer still satisfies KRA for a chain going live now cannot be determined from the code. | Potential compliance blocker at go-live | Client tax advisor |
| 2 | **Daraja production credentials and callback URL.** Requires a registered Safaricom shortcode, a public HTTPS domain, and Safaricom-side whitelisting. Long lead time. | Blocks M-PESA go-live | Client / Safaricom |
| 3 | **VAT figures in the source document do not reconcile** (§4.2). Expected values will be recomputed and changes listed. | Acceptance test rework | This build |
| 4 | **US-PRQ-03 threshold contradiction** (§4.5). Seeded from the acceptance criteria pending confirmation. | Configuration only | Client finance |
| 5 | **POS JS rewrite risk** (§5). The 17 to 18 POS frontend changes are substantial; the fiscal module's OWL patches need rewriting, not porting. | Schedule risk on `retail_fiscal_ke` | This build |
| 6 | **`custom_pos` dependency scope.** `custom_esd_pos_account_novitus` depends on Deylin's `custom_pos`; how much of it is genuinely needed is not yet established. | Possible scope increase | This build, during port |

---

## 10. Traceability

| Story | Module | Mechanism |
|---|---|---|
| US-POS-01, 03, 05, 08 | — | Standard CE configuration |
| US-POS-02 | `retail_pos` | Standard scan plus zero-qty guard |
| US-POS-04 | `retail_mpesa_pos` | STK push and manual reference |
| US-POS-06 | `retail_base` | `loyalty.program` configuration |
| US-POS-07 | `retail_pos` | Standard refund plus 7-day window rule |
| US-STK-01 to 06 | `retail_stock_requisition` | Six-state machine |
| US-PRQ-01 to 03 | `retail_purchase_request` | Request plus threshold approval |
| US-PRQ-04 | — | Standard receipt picking |
| US-RPT-01 to 04 | `retail_pos_report` | `action_generate()` plus xlsx |
