# Tano Retail — Odoo 18 CE

Custom Odoo 18 Community modules for Kenyan supermarket retail operations:
point of sale, stock requisition between the central warehouse and branches,
purchase requests, and POS sales reporting.

These are standard Odoo addons. They contain no machine-specific configuration
and install on any Odoo 18 CE instance.

---

## Installation

1. Copy or symlink the `addons/` directory into your instance's addons path,
   or append this repository's `addons/` directory to `addons_path` in your
   `odoo.conf`:

   ```ini
   addons_path = /opt/odoo/addons,/srv/Retail/addons
   ```

2. Restart Odoo and update the apps list.

3. Install `retail_base` first, then the modules you need. Dependencies
   resolve automatically:

   ```bash
   odoo-bin -d <database> -i retail_base,retail_stock_requisition
   ```

`config/odoo.conf.example` is a starting point for a development instance.
It is a convenience, not a deployment artefact.

---

## Modules

| Module | Status | Purpose |
|---|---|---|
| `retail_base` | Complete | Security groups, branch warehouses, user branch scoping, product departments, loyalty programme |
| `retail_stock_requisition` | Complete | Six-state branch replenishment workflow with internal transfer creation |
| `retail_fiscal_ke` | Planned | Kenyan fiscal classification and ESD printing (port of a v17 module) |
| `retail_pos` | Planned | Zero-quantity block, receipt layout, return window |
| `retail_mpesa_base` / `retail_mpesa_pos` | Planned | Safaricom Daraja integration and POS payment method |
| `retail_purchase_request` | Planned | Purchase requests with threshold-based approval |
| `retail_pos_report` | Planned | Daily and per-item sales summary with XLSX export |

### `retail_base`

- Four security groups under a "Tano Retail" category: Supply Chain Officer,
  Finance Officer, Procurement Manager, CFO. The CFO group implies
  Procurement Manager.
- `res.users.retail_warehouse_ids` scopes a user to specific branches. An
  empty assignment means unrestricted, so head office staff are not locked out.
- Central Warehouse plus four branch warehouses.
- Department to category product hierarchy, used for sales-report grouping.
- Tano Points loyalty programme: 1 point per KES 10 spent, each point
  redeeming for KES 0.10.

### `retail_stock_requisition`

State machine:

```
draft -> submitted -> sc_validated -> finance_approved -> done
  |          |             |
cancel     cancel        reject
  |          |             |
cancelled  cancelled    rejected -> (reset to draft) -> draft
```

- Submission is blocked when the destination branch is not assigned to the
  requestor.
- Finance approval creates an internal `stock.picking` carrying **approved**
  quantities, not requested ones. Lines approved at zero are omitted.
- Validating that transfer closes the requisition automatically.
- Cancellation is refused once a requisition reaches finance approval.
- Rejection requires a reason, which is stamped along with the rejector.

---

## Running the tests

The modules ship with an automated test suite. Every acceptance case from the
requirements document is a named test, so `TC-STK-01` maps to
`test_tc_stk_01_full_approval_flow`.

```bash
odoo-bin -d <test-database> \
  -i retail_base,retail_stock_requisition \
  --test-enable --stop-after-init
```

Current status on Odoo 18.0 CE: **44 tests, 0 failed, 0 errors.**

| Test case | Test method |
|---|---|
| TC-STK-01 | `test_tc_stk_01_full_approval_flow` |
| TC-STK-02 | `test_tc_stk_02_unauthorised_station_blocked` |
| TC-STK-03 | `test_tc_stk_03_rejection_stamps_reason_and_rejector` |

---

## Documentation

- Design specification: `docs/superpowers/specs/2026-08-25-tano-retail-odoo18-design.md`
- Phase 1 implementation plan: `docs/superpowers/plans/2026-08-25-phase1-base-and-requisition.md`

The specification records open risks that need decisions before production
use, including KRA eTIMS compliance and Safaricom Daraja callback
requirements.

---

## Requirements

- Odoo 18.0 Community Edition
- Python 3.12
- PostgreSQL 12 or later

Additional Python dependencies for the planned modules are listed in
`requirements.txt`.
