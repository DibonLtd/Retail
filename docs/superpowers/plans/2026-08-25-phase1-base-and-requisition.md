# Tano Retail Phase 1 — Foundation and Stock Requisition

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable Odoo 18 CE foundation module plus a complete six-state stock requisition workflow that moves real stock from the central warehouse to a branch.

**Architecture:** Two Odoo modules. `retail_base` supplies the company, branch warehouses, six security groups, product department hierarchy, loyalty program, and the `res.users.retail_warehouse_ids` field that scopes users to branches. `retail_stock_requisition` adds a `mail.thread` requisition model with a six-state approval chain that creates an internal `stock.picking` on finance approval and closes itself when that picking is validated.

**Tech Stack:** Odoo 18.0 Community, Python 3.12, PostgreSQL 16, Odoo's `TransactionCase` test framework.

**Spec:** `docs/superpowers/specs/2026-08-25-tano-retail-odoo18-design.md`

## Global Constraints

- Target Odoo **18.0 Community Edition** only. No Enterprise modules (`approvals`, `l10n_ke_edi_oscu`) may be depended upon.
- Module version strings are `18.0.1.0.0`.
- Odoo 18 renamed the list view tag: use `<list>`, never `<tree>`.
- Odoo 18 removed `name_get()`. Use `_compute_display_name`.
- Currency is KES throughout. Never hardcode a currency symbol in Python.
- Module technical names are prefixed `retail_`.
- Every `TC-*` acceptance case becomes a test method named `test_tc_<id>_<description>`.
- Licence for all modules: `LGPL-3`.
- No secrets in git. Credentials belong in `ir.config_parameter`.
- Branch modelling uses native `stock.warehouse`. Do not invent a "station" model.

## Runtime

Local portable stack, no admin rights, no Docker:

| Component | Location |
|---|---|
| PostgreSQL 16 | `C:\Users\orega\odoo18-dev\pgsql` on port **5433** |
| Data directory | `C:\Users\orega\odoo18-dev\pgdata` |
| Odoo 18 CE source | `C:\Users\orega\odoo18-dev\odoo18` |
| Python venv | `C:\Users\orega\odoo18-dev\venv` (Python 3.12.3) |
| Custom addons | `C:\Users\orega\Documents\GitHub\Retail\addons` |

Test command used throughout this plan:

```bash
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe \
  C:/Users/orega/odoo18-dev/odoo18/odoo-bin \
  -c C:/Users/orega/Documents/GitHub/Retail/config/odoo.conf \
  -d tano_test -i <module> --test-enable --stop-after-init \
  --test-tags /<module>
```

---

## File Structure

### `addons/retail_base/`

| File | Responsibility |
|---|---|
| `__manifest__.py` | Module metadata, dependency list, data file ordering |
| `models/res_users.py` | `retail_warehouse_ids` field and the `_check_retail_warehouse` helper |
| `security/retail_groups.xml` | Module category and the four new security groups |
| `security/ir.model.access.csv` | Access rules (empty of new models in this module) |
| `views/res_users_views.xml` | Warehouse assignment on the user form |
| `data/warehouse_data.xml` | Central Warehouse plus four branch warehouses |
| `data/product_category_data.xml` | Department → category hierarchy |
| `data/loyalty_program_data.xml` | Earn/redeem rates |
| `tests/test_security_groups.py` | Groups resolve and nest correctly |
| `tests/test_user_warehouses.py` | Field behaviour and helper |
| `tests/test_master_data.py` | Warehouses and categories exist with correct parents |

### `addons/retail_stock_requisition/`

| File | Responsibility |
|---|---|
| `__manifest__.py` | Metadata and data ordering |
| `models/requisition.py` | `retail.stock.requisition` — fields, state machine, notifications |
| `models/requisition_line.py` | `retail.stock.requisition.line` — quantities and computes |
| `models/stock_picking.py` | `button_validate` override closing the requisition |
| `wizard/reject_wizard.py` | `retail.requisition.reject.wizard` |
| `data/ir_sequence.xml` | `RSR/%(year)s/#####` sequence |
| `data/mail_templates.xml` | Submit / validate / approve / reject notification templates |
| `security/requisition_groups.xml` | Record rules |
| `security/ir.model.access.csv` | Model access per group |
| `views/requisition_views.xml` | Form, list, kanban, search |
| `views/menus.xml` | Menu entries |
| `wizard/reject_wizard_views.xml` | Wizard form |
| `tests/test_requisition_flow.py` | TC-STK-01 happy path |
| `tests/test_requisition_authorisation.py` | TC-STK-02 blocked station |
| `tests/test_requisition_rejection.py` | TC-STK-03 reject and resubmit |
| `tests/test_requisition_guards.py` | Cancel guard (US-STK-06) |

---

## Task 1: Runtime and repository scaffold

**Files:**
- Create: `config/odoo.conf`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `README.md`
- Create: `addons/.gitkeep`

**Interfaces:**
- Consumes: nothing
- Produces: a working `odoo-bin` invocation and the `config/odoo.conf` path every later task's test command uses.

- [ ] **Step 1: Initialise the PostgreSQL cluster**

```bash
C:/Users/orega/odoo18-dev/pgsql/bin/initdb.exe \
  -D C:/Users/orega/odoo18-dev/pgdata \
  -U odoo --auth-local=trust --auth-host=trust -E UTF8
```

Expected: `Success. You can now start the database server using...`

- [ ] **Step 2: Start PostgreSQL on port 5433**

```bash
C:/Users/orega/odoo18-dev/pgsql/bin/pg_ctl.exe \
  -D C:/Users/orega/odoo18-dev/pgdata \
  -o "-p 5433" -l C:/Users/orega/odoo18-dev/pg.log start
```

Verify: `C:/Users/orega/odoo18-dev/pgsql/bin/psql.exe -p 5433 -U odoo -d postgres -c "select version();"`
Expected: PostgreSQL 16.x version string.

- [ ] **Step 3: Install Odoo 18 Python requirements**

```bash
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe -m pip install --upgrade pip wheel
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe -m pip install -r C:/Users/orega/odoo18-dev/odoo18/requirements.txt
```

Expected: all wheels install. If `python-ldap` fails, it is optional on Windows — remove that line and continue.

- [ ] **Step 4: Write `config/odoo.conf`**

```ini
[options]
addons_path = C:/Users/orega/odoo18-dev/odoo18/addons,C:/Users/orega/Documents/GitHub/Retail/addons
db_host = localhost
db_port = 5433
db_user = odoo
db_password = False
db_name = tano_dev
http_port = 8069
log_level = info
without_demo = False
```

Note: `http_port` 8069 collides with the running Odoo 19 service. If Odoo fails to bind, change to 8070.

- [ ] **Step 5: Write `requirements.txt`**

```text
# Odoo 18 CE core requirements are installed separately from the Odoo source tree.
# These are the additional dependencies introduced by Tano Retail modules.
xlsxwriter>=3.1.0
xmltodict>=0.13.0
pyqrcode>=1.2.1
pypng>=0.20220715.0
```

- [ ] **Step 6: Write `.gitignore`**

```text
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
*.log
.DS_Store
.idea/
.vscode/
*.sqlite
```

- [ ] **Step 7: Verify Odoo boots against an empty addons directory**

```bash
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe \
  C:/Users/orega/odoo18-dev/odoo18/odoo-bin \
  -c C:/Users/orega/Documents/GitHub/Retail/config/odoo.conf \
  -d tano_test --stop-after-init -i base
```

Expected: log ends with `Modules loaded.` and exit code 0.

- [ ] **Step 8: Commit**

```bash
git add config requirements.txt .gitignore README.md addons/.gitkeep
git commit -m "chore: add Odoo 18 runtime config and repo scaffold"
```

---

## Task 2: `retail_base` skeleton and security groups

**Files:**
- Create: `addons/retail_base/__init__.py`
- Create: `addons/retail_base/__manifest__.py`
- Create: `addons/retail_base/security/retail_groups.xml`
- Test: `addons/retail_base/tests/__init__.py`, `addons/retail_base/tests/test_security_groups.py`

**Interfaces:**
- Consumes: Task 1's `config/odoo.conf`
- Produces: XML IDs `retail_base.group_supply_chain_officer`, `retail_base.group_finance_officer`, `retail_base.group_procurement_manager`, `retail_base.group_purchase_cfo`, and category `retail_base.module_category_tano_retail`. Every later task references these exact IDs.

- [ ] **Step 1: Write the failing test**

`addons/retail_base/tests/test_security_groups.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSecurityGroups(TransactionCase):

    def test_retail_groups_exist(self):
        """The four Tano Retail approval groups are installed."""
        for xmlid in (
            "retail_base.group_supply_chain_officer",
            "retail_base.group_finance_officer",
            "retail_base.group_procurement_manager",
            "retail_base.group_purchase_cfo",
        ):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(group, "Missing security group %s" % xmlid)

    def test_groups_are_in_tano_category(self):
        """Groups are filed under the Tano Retail module category."""
        category = self.env.ref("retail_base.module_category_tano_retail")
        group = self.env.ref("retail_base.group_supply_chain_officer")
        self.assertEqual(group.category_id, category)

    def test_cfo_implies_procurement_manager(self):
        """A CFO inherits procurement manager rights."""
        cfo = self.env.ref("retail_base.group_purchase_cfo")
        procurement = self.env.ref("retail_base.group_procurement_manager")
        self.assertIn(procurement, cfo.implied_ids)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe C:/Users/orega/odoo18-dev/odoo18/odoo-bin -c config/odoo.conf -d tano_test -i retail_base --test-enable --stop-after-init --test-tags /retail_base
```
Expected: FAIL — module `retail_base` not found.

- [ ] **Step 3: Write `__manifest__.py`**

```python
{
    "name": "Tano Retail Base",
    "summary": "Foundation data, branches and security groups for Tano Supermarket",
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": [
        "base",
        "stock",
        "point_of_sale",
        "loyalty",
    ],
    "data": [
        "security/retail_groups.xml",
        "views/res_users_views.xml",
        "data/warehouse_data.xml",
        "data/product_category_data.xml",
        "data/loyalty_program_data.xml",
    ],
    "installable": True,
    "application": False,
}
```

Note: `views/res_users_views.xml` and the three data files arrive in Tasks 3–5. Until then, comment out the lines for files that do not yet exist, or create empty stub files with a bare `<odoo/>` root. Prefer the stub, so the manifest is written once.

- [ ] **Step 4: Write `__init__.py`**

```python
from . import models
```

Create `addons/retail_base/models/__init__.py` as an empty file for now, and `addons/retail_base/tests/__init__.py` containing:

```python
from . import test_security_groups
```

- [ ] **Step 5: Write `security/retail_groups.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="module_category_tano_retail" model="ir.module.category">
        <field name="name">Tano Retail</field>
        <field name="description">Roles for Tano Supermarket retail operations</field>
        <field name="sequence">20</field>
    </record>

    <record id="group_supply_chain_officer" model="res.groups">
        <field name="name">Supply Chain Officer</field>
        <field name="category_id" ref="module_category_tano_retail"/>
        <field name="comment">Validates stock requisitions and adjusts approved quantities.</field>
    </record>

    <record id="group_finance_officer" model="res.groups">
        <field name="name">Finance Officer</field>
        <field name="category_id" ref="module_category_tano_retail"/>
        <field name="comment">Approves requisitions and reviews all sales reporting.</field>
    </record>

    <record id="group_procurement_manager" model="res.groups">
        <field name="name">Procurement Manager</field>
        <field name="category_id" ref="module_category_tano_retail"/>
        <field name="comment">Approves purchase requests and raises RFQs.</field>
    </record>

    <record id="group_purchase_cfo" model="res.groups">
        <field name="name">CFO</field>
        <field name="category_id" ref="module_category_tano_retail"/>
        <field name="implied_ids" eval="[(4, ref('group_procurement_manager'))]"/>
        <field name="comment">Top-tier approval for high-value purchase orders.</field>
    </record>
</odoo>
```

- [ ] **Step 6: Run the test to verify it passes**

Run the Step 2 command.
Expected: 3 tests pass, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add addons/retail_base
git commit -m "feat(retail_base): add Tano Retail security groups"
```

---

## Task 3: Branch scoping on users

**Files:**
- Create: `addons/retail_base/models/res_users.py`
- Create: `addons/retail_base/views/res_users_views.xml`
- Modify: `addons/retail_base/models/__init__.py`
- Test: `addons/retail_base/tests/test_user_warehouses.py`

**Interfaces:**
- Consumes: `retail_base.group_supply_chain_officer` from Task 2
- Produces: `res.users.retail_warehouse_ids` (Many2many to `stock.warehouse`) and `res.users._is_warehouse_allowed(warehouse)` returning `bool`. Task 8 calls `_is_warehouse_allowed` to enforce TC-STK-02.

- [ ] **Step 1: Write the failing test**

`addons/retail_base/tests/test_user_warehouses.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestUserWarehouses(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wh_westgate = cls.env["stock.warehouse"].create(
            {"name": "Westgate Branch", "code": "WGT"}
        )
        cls.wh_citymall = cls.env["stock.warehouse"].create(
            {"name": "City Mall Branch", "code": "CTM"}
        )
        cls.user = cls.env["res.users"].create(
            {
                "name": "Agnes Wanjiku",
                "login": "agnes.test",
                "retail_warehouse_ids": [(6, 0, [cls.wh_westgate.id])],
            }
        )

    def test_assigned_warehouse_is_allowed(self):
        self.assertTrue(self.user._is_warehouse_allowed(self.wh_westgate))

    def test_unassigned_warehouse_is_not_allowed(self):
        self.assertFalse(self.user._is_warehouse_allowed(self.wh_citymall))

    def test_user_with_no_assignment_is_allowed_everywhere(self):
        """An empty assignment means unrestricted, so head office is not locked out."""
        head_office = self.env["res.users"].create(
            {"name": "Joseph Mwangi", "login": "joseph.test"}
        )
        self.assertTrue(head_office._is_warehouse_allowed(self.wh_citymall))
```

- [ ] **Step 2: Run the test to verify it fails**

Run the Task 2 Step 2 command with `-u retail_base`.
Expected: FAIL — `Invalid field 'retail_warehouse_ids' on model 'res.users'`.

- [ ] **Step 3: Write `models/res_users.py`**

```python
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    retail_warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        relation="retail_user_warehouse_rel",
        column1="user_id",
        column2="warehouse_id",
        string="Assigned Branches",
        help=(
            "Branches this user may transact against. "
            "Leave empty to allow all branches, which is the usual "
            "setting for head office staff."
        ),
    )

    def _is_warehouse_allowed(self, warehouse):
        """Return True if this user may transact against ``warehouse``.

        An empty assignment is treated as unrestricted so that head office
        roles are not locked out by default.
        """
        self.ensure_one()
        if not self.retail_warehouse_ids:
            return True
        return warehouse in self.retail_warehouse_ids
```

Set `addons/retail_base/models/__init__.py` to:

```python
from . import res_users
```

- [ ] **Step 4: Write `views/res_users_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_users_form_retail" model="ir.ui.view">
        <field name="name">res.users.form.retail</field>
        <field name="model">res.users</field>
        <field name="inherit_id" ref="base.view_users_form"/>
        <field name="arch" type="xml">
            <xpath expr="//notebook" position="inside">
                <page string="Retail Branches" name="retail_branches">
                    <field name="retail_warehouse_ids" widget="many2many_tags"/>
                </page>
            </xpath>
        </field>
    </record>
</odoo>
```

- [ ] **Step 5: Run the test to verify it passes**

Add `from . import test_user_warehouses` to `tests/__init__.py`, then run the Step 2 command.
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add addons/retail_base
git commit -m "feat(retail_base): scope users to branch warehouses"
```

---

## Task 4: Branch and warehouse master data

**Files:**
- Create: `addons/retail_base/data/warehouse_data.xml`
- Test: `addons/retail_base/tests/test_master_data.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: XML IDs `retail_base.warehouse_central`, `warehouse_westgate`, `warehouse_thika_road`, `warehouse_junction`, `warehouse_city_mall`. Tests in Task 8 onward reference `retail_base.warehouse_central` and `retail_base.warehouse_westgate`.

- [ ] **Step 1: Write the failing test**

`addons/retail_base/tests/test_master_data.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMasterData(TransactionCase):

    def test_all_branches_exist(self):
        for xmlid in (
            "retail_base.warehouse_central",
            "retail_base.warehouse_westgate",
            "retail_base.warehouse_thika_road",
            "retail_base.warehouse_junction",
            "retail_base.warehouse_city_mall",
        ):
            warehouse = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(warehouse, "Missing warehouse %s" % xmlid)

    def test_branches_have_stock_locations(self):
        """Each branch must expose a stock location for requisition transfers."""
        westgate = self.env.ref("retail_base.warehouse_westgate")
        self.assertTrue(westgate.lot_stock_id)
        self.assertEqual(westgate.lot_stock_id.usage, "internal")

    def test_warehouse_codes_are_unique(self):
        warehouses = self.env["stock.warehouse"].search([])
        codes = warehouses.mapped("code")
        self.assertEqual(len(codes), len(set(codes)))
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_base`.
Expected: FAIL — `Missing warehouse retail_base.warehouse_central`.

- [ ] **Step 3: Write `data/warehouse_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="warehouse_central" model="stock.warehouse">
        <field name="name">Central Warehouse</field>
        <field name="code">CW</field>
    </record>

    <record id="warehouse_westgate" model="stock.warehouse">
        <field name="name">Westgate Branch</field>
        <field name="code">WGT</field>
    </record>

    <record id="warehouse_thika_road" model="stock.warehouse">
        <field name="name">Thika Road Mall Branch</field>
        <field name="code">TRM</field>
    </record>

    <record id="warehouse_junction" model="stock.warehouse">
        <field name="name">Junction Branch</field>
        <field name="code">JCT</field>
    </record>

    <record id="warehouse_city_mall" model="stock.warehouse">
        <field name="name">City Mall Branch</field>
        <field name="code">CTM</field>
    </record>
</odoo>
```

Note: Odoo creates `lot_stock_id` and the picking types for each warehouse automatically. Warehouse codes are limited to five characters.

- [ ] **Step 4: Run the test to verify it passes**

Add `from . import test_master_data` to `tests/__init__.py`, then run.
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/retail_base
git commit -m "feat(retail_base): add central warehouse and four branches"
```

---

## Task 5: Product departments and loyalty programme

**Files:**
- Create: `addons/retail_base/data/product_category_data.xml`
- Create: `addons/retail_base/data/loyalty_program_data.xml`
- Modify: `addons/retail_base/tests/test_master_data.py`

**Interfaces:**
- Consumes: nothing
- Produces: XML IDs `retail_base.categ_dry_foods`, `categ_flour_grains`, `categ_dairy`, `categ_fresh_dairy`, `categ_household`, `categ_cleaning`, `categ_personal_care`, `categ_oral_care`, and `retail_base.loyalty_tano_points`. Phase 4's sales report resolves departments by walking `categ_id.parent_id` to the top level.

- [ ] **Step 1: Write the failing test**

Append to `addons/retail_base/tests/test_master_data.py`:

```python
    def test_department_hierarchy(self):
        """Categories nest as Department -> Category, which the sales report groups by."""
        pairs = (
            ("retail_base.categ_flour_grains", "retail_base.categ_dry_foods"),
            ("retail_base.categ_fresh_dairy", "retail_base.categ_dairy"),
            ("retail_base.categ_cleaning", "retail_base.categ_household"),
            ("retail_base.categ_oral_care", "retail_base.categ_personal_care"),
        )
        for child_xmlid, parent_xmlid in pairs:
            child = self.env.ref(child_xmlid)
            parent = self.env.ref(parent_xmlid)
            self.assertEqual(child.parent_id, parent)

    def test_loyalty_programme_rates(self):
        """1 point per KES 10 spent; each point redeems for KES 0.10."""
        programme = self.env.ref("retail_base.loyalty_tano_points")
        self.assertEqual(programme.program_type, "loyalty")
        rule = programme.rule_ids[:1]
        self.assertTrue(rule, "Loyalty programme has no earn rule")
        self.assertAlmostEqual(rule.reward_point_amount, 0.1, places=4)
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_base`.
Expected: FAIL — missing `retail_base.categ_flour_grains`.

- [ ] **Step 3: Write `data/product_category_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="categ_dry_foods" model="product.category">
        <field name="name">Dry Foods</field>
        <field name="parent_id" ref="product.product_category_all"/>
    </record>
    <record id="categ_flour_grains" model="product.category">
        <field name="name">Flour &amp; Grains</field>
        <field name="parent_id" ref="categ_dry_foods"/>
    </record>

    <record id="categ_dairy" model="product.category">
        <field name="name">Dairy</field>
        <field name="parent_id" ref="product.product_category_all"/>
    </record>
    <record id="categ_fresh_dairy" model="product.category">
        <field name="name">Fresh Dairy</field>
        <field name="parent_id" ref="categ_dairy"/>
    </record>

    <record id="categ_household" model="product.category">
        <field name="name">Household</field>
        <field name="parent_id" ref="product.product_category_all"/>
    </record>
    <record id="categ_cleaning" model="product.category">
        <field name="name">Cleaning</field>
        <field name="parent_id" ref="categ_household"/>
    </record>

    <record id="categ_personal_care" model="product.category">
        <field name="name">Personal Care</field>
        <field name="parent_id" ref="product.product_category_all"/>
    </record>
    <record id="categ_oral_care" model="product.category">
        <field name="name">Oral Care</field>
        <field name="parent_id" ref="categ_personal_care"/>
    </record>
</odoo>
```

- [ ] **Step 4: Write `data/loyalty_program_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="loyalty_tano_points" model="loyalty.program">
        <field name="name">Tano Points</field>
        <field name="program_type">loyalty</field>
        <field name="trigger">auto</field>
        <field name="portal_visible" eval="True"/>
        <field name="portal_point_name">Points</field>
    </record>

    <record id="loyalty_tano_points_rule" model="loyalty.rule">
        <field name="program_id" ref="loyalty_tano_points"/>
        <field name="reward_point_mode">money</field>
        <field name="reward_point_amount">0.1</field>
    </record>

    <record id="loyalty_tano_points_reward" model="loyalty.reward">
        <field name="program_id" ref="loyalty_tano_points"/>
        <field name="reward_type">discount</field>
        <field name="discount_mode">per_point</field>
        <field name="discount">0.1</field>
        <field name="required_points">1</field>
    </record>
</odoo>
```

Note: `reward_point_amount` of 0.1 in `money` mode means 0.1 points per currency unit, which is 1 point per KES 10. `discount` of 0.1 in `per_point` mode redeems each point for KES 0.10. Both match the source document, where 340 points equals KES 34.

- [ ] **Step 5: Run the test to verify it passes**

Run with `-u retail_base`.
Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add addons/retail_base
git commit -m "feat(retail_base): add product departments and Tano Points loyalty"
```

---

## Task 6: `retail_stock_requisition` skeleton, sequence and model

**Files:**
- Create: `addons/retail_stock_requisition/__init__.py`
- Create: `addons/retail_stock_requisition/__manifest__.py`
- Create: `addons/retail_stock_requisition/models/__init__.py`
- Create: `addons/retail_stock_requisition/models/requisition.py`
- Create: `addons/retail_stock_requisition/models/requisition_line.py`
- Create: `addons/retail_stock_requisition/data/ir_sequence.xml`
- Create: `addons/retail_stock_requisition/security/ir.model.access.csv`
- Test: `addons/retail_stock_requisition/tests/__init__.py`, `tests/test_requisition_model.py`

**Interfaces:**
- Consumes: `retail_base.warehouse_central`, `retail_base.warehouse_westgate`, and the four groups from Task 2.
- Produces: model `retail.stock.requisition` with fields `name`, `state`, `requestor_id`, `source_location_id`, `dest_warehouse_id`, `date_required`, `line_ids`, `picking_ids`, `rejection_reason`, `rejected_by_id`, `sc_validated_by_id`, `sc_validated_date`, `finance_approved_by_id`, `finance_approved_date`; and `retail.stock.requisition.line` with `product_id`, `product_uom_id`, `qty_requested`, `qty_approved`, `qty_received`, `qty_available_source`. Tasks 7–10 add behaviour to these exact names.

- [ ] **Step 1: Write the failing test**

`addons/retail_stock_requisition/tests/test_requisition_model.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.product = cls.env["product.product"].create(
            {"name": "Bidii Unga Maize Flour 2kg", "type": "consu", "is_storable": True}
        )

    def _new_requisition(self):
        return self.env["retail.stock.requisition"].create(
            {
                "source_location_id": self.central.lot_stock_id.id,
                "dest_warehouse_id": self.westgate.id,
                "line_ids": [
                    (0, 0, {"product_id": self.product.id, "qty_requested": 100.0})
                ],
            }
        )

    def test_reference_is_generated(self):
        requisition = self._new_requisition()
        self.assertTrue(requisition.name.startswith("RSR/"))
        self.assertNotEqual(requisition.name, "New")

    def test_starts_in_draft(self):
        self.assertEqual(self._new_requisition().state, "draft")

    def test_requestor_defaults_to_current_user(self):
        self.assertEqual(self._new_requisition().requestor_id, self.env.user)

    def test_approved_qty_defaults_to_requested(self):
        requisition = self._new_requisition()
        self.assertEqual(requisition.line_ids.qty_approved, 100.0)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe C:/Users/orega/odoo18-dev/odoo18/odoo-bin -c config/odoo.conf -d tano_test -i retail_stock_requisition --test-enable --stop-after-init --test-tags /retail_stock_requisition
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write `__manifest__.py`**

```python
{
    "name": "Tano Retail Stock Requisition",
    "summary": "Branch stock requisition with supply chain and finance approval",
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_base", "stock", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/requisition_groups.xml",
        "data/ir_sequence.xml",
        "data/mail_templates.xml",
        "wizard/reject_wizard_views.xml",
        "views/requisition_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
```

Create stub `<odoo/>` files for any data file not yet written so the manifest is written once.

- [ ] **Step 4: Write `data/ir_sequence.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="seq_retail_stock_requisition" model="ir.sequence">
        <field name="name">Retail Stock Requisition</field>
        <field name="code">retail.stock.requisition</field>
        <field name="prefix">RSR/%(year)s/</field>
        <field name="padding">5</field>
        <field name="company_id" eval="False"/>
    </record>
</odoo>
```

- [ ] **Step 5: Write `models/requisition.py`**

```python
from odoo import api, fields, models

REQUISITION_STATES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("sc_validated", "SC Validated"),
    ("finance_approved", "Finance Approved"),
    ("done", "Done"),
    ("rejected", "Rejected"),
    ("cancelled", "Cancelled"),
]


class RetailStockRequisition(models.Model):
    _name = "retail.stock.requisition"
    _description = "Retail Stock Requisition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    state = fields.Selection(
        selection=REQUISITION_STATES,
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    requestor_id = fields.Many2one(
        comodel_name="res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    source_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Source Location",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    dest_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Destination Branch",
        required=True,
        tracking=True,
    )
    dest_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Destination Location",
        compute="_compute_dest_location_id",
        store=True,
        readonly=False,
    )
    date_required = fields.Date(string="Required By")
    line_ids = fields.One2many(
        comodel_name="retail.stock.requisition.line",
        inverse_name="requisition_id",
        string="Products",
        copy=True,
    )
    picking_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="requisition_id",
        string="Transfers",
        readonly=True,
    )
    picking_count = fields.Integer(compute="_compute_picking_count")
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    rejection_reason = fields.Text(readonly=True, copy=False)
    rejected_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    sc_validated_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    sc_validated_date = fields.Datetime(readonly=True, copy=False)
    finance_approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    finance_approved_date = fields.Datetime(readonly=True, copy=False)

    @api.depends("dest_warehouse_id")
    def _compute_dest_location_id(self):
        for requisition in self:
            requisition.dest_location_id = requisition.dest_warehouse_id.lot_stock_id

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for requisition in self:
            requisition.picking_count = len(requisition.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "retail.stock.requisition"
                ) or "New"
        return super().create(vals_list)
```

- [ ] **Step 6: Write `models/requisition_line.py`**

```python
from odoo import api, fields, models


class RetailStockRequisitionLine(models.Model):
    _name = "retail.stock.requisition.line"
    _description = "Retail Stock Requisition Line"

    requisition_id = fields.Many2one(
        comodel_name="retail.stock.requisition",
        string="Requisition",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
    )
    qty_requested = fields.Float(
        string="Requested Qty",
        default=1.0,
        digits="Product Unit of Measure",
    )
    qty_approved = fields.Float(
        string="Approved Qty",
        compute="_compute_qty_approved",
        store=True,
        readonly=False,
        digits="Product Unit of Measure",
        help="Quantity endorsed by the supply chain officer.",
    )
    qty_received = fields.Float(
        string="Received Qty",
        compute="_compute_qty_received",
        digits="Product Unit of Measure",
    )
    qty_available_source = fields.Float(
        string="Available at Source",
        compute="_compute_qty_available_source",
        digits="Product Unit of Measure",
        help="On-hand quantity at the requisition source location.",
    )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    @api.depends("qty_requested")
    def _compute_qty_approved(self):
        for line in self:
            line.qty_approved = line.qty_requested

    @api.depends("requisition_id.picking_ids.state", "product_id")
    def _compute_qty_received(self):
        for line in self:
            moves = line.requisition_id.picking_ids.move_ids.filtered(
                lambda m, line=line: m.product_id == line.product_id
                and m.state == "done"
            )
            line.qty_received = sum(moves.mapped("quantity"))

    @api.depends("product_id", "requisition_id.source_location_id")
    def _compute_qty_available_source(self):
        for line in self:
            location = line.requisition_id.source_location_id
            if not line.product_id or not location:
                line.qty_available_source = 0.0
                continue
            line.qty_available_source = line.product_id.with_context(
                location=location.id
            ).qty_available
```

Note: `picking_ids` needs `requisition_id` on `stock.picking`, added in Task 9. Until then, temporarily declare `picking_ids` as a plain `Many2many` or add the `stock.picking` field first. The plan adds it in Task 9; if the module will not install before then, create `models/stock_picking.py` with only the field now.

- [ ] **Step 7: Write `security/ir.model.access.csv`**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_requisition_pos_manager,requisition.pos.manager,model_retail_stock_requisition,point_of_sale.group_pos_manager,1,1,1,0
access_requisition_supply_chain,requisition.supply.chain,model_retail_stock_requisition,retail_base.group_supply_chain_officer,1,1,1,0
access_requisition_finance,requisition.finance,model_retail_stock_requisition,retail_base.group_finance_officer,1,1,1,0
access_requisition_line_pos_manager,requisition.line.pos.manager,model_retail_stock_requisition_line,point_of_sale.group_pos_manager,1,1,1,1
access_requisition_line_supply_chain,requisition.line.supply.chain,model_retail_stock_requisition_line,retail_base.group_supply_chain_officer,1,1,1,1
access_requisition_line_finance,requisition.line.finance,model_retail_stock_requisition_line,retail_base.group_finance_officer,1,1,1,1
```

- [ ] **Step 8: Write `__init__.py` files**

`addons/retail_stock_requisition/__init__.py`:

```python
from . import models
from . import wizard
```

`addons/retail_stock_requisition/models/__init__.py`:

```python
from . import requisition
from . import requisition_line
from . import stock_picking
```

`addons/retail_stock_requisition/tests/__init__.py`:

```python
from . import test_requisition_model
```

- [ ] **Step 9: Run the test to verify it passes**

Run the Step 2 command.
Expected: 4 tests pass.

- [ ] **Step 10: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): add requisition model, lines and sequence"
```

---

## Task 7: Submit with branch authorisation (TC-STK-02)

**Files:**
- Modify: `addons/retail_stock_requisition/models/requisition.py`
- Test: `addons/retail_stock_requisition/tests/test_requisition_authorisation.py`

**Interfaces:**
- Consumes: `res.users._is_warehouse_allowed(warehouse)` from Task 3.
- Produces: `action_submit()` on `retail.stock.requisition`, raising `UserError` when the destination is not assigned to the requestor.

- [ ] **Step 1: Write the failing test**

`addons/retail_stock_requisition/tests/test_requisition_authorisation.py`:

```python
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionAuthorisation(TransactionCase):
    """TC-STK-02: submission to an unassigned branch is blocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.city_mall = cls.env.ref("retail_base.warehouse_city_mall")
        cls.product = cls.env["product.product"].create(
            {"name": "Royco Mchuzi Mix 200g", "type": "consu", "is_storable": True}
        )
        cls.agnes = cls.env["res.users"].create(
            {
                "name": "Agnes Wanjiku",
                "login": "agnes.auth.test",
                "groups_id": [
                    (4, cls.env.ref("point_of_sale.group_pos_manager").id),
                ],
                "retail_warehouse_ids": [(6, 0, [cls.westgate.id])],
            }
        )

    def _requisition_for(self, warehouse):
        return (
            self.env["retail.stock.requisition"]
            .with_user(self.agnes)
            .create(
                {
                    "source_location_id": self.central.lot_stock_id.id,
                    "dest_warehouse_id": warehouse.id,
                    "line_ids": [
                        (0, 0, {"product_id": self.product.id, "qty_requested": 10.0})
                    ],
                }
            )
        )

    def test_tc_stk_02_unauthorised_station_blocked(self):
        requisition = self._requisition_for(self.city_mall)
        with self.assertRaises(UserError) as ctx:
            requisition.with_user(self.agnes).action_submit()
        self.assertIn("City Mall Branch", str(ctx.exception))
        self.assertEqual(requisition.state, "draft")

    def test_assigned_station_submits_successfully(self):
        requisition = self._requisition_for(self.westgate)
        requisition.with_user(self.agnes).action_submit()
        self.assertEqual(requisition.state, "submitted")
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_stock_requisition`.
Expected: FAIL — `'retail.stock.requisition' object has no attribute 'action_submit'`.

- [ ] **Step 3: Add `action_submit` to `models/requisition.py`**

Add the import at the top of the file:

```python
from odoo.exceptions import UserError
```

Add these methods to the `RetailStockRequisition` class:

```python
    def _check_destination_authorised(self):
        """Raise if the requestor may not transact against the destination."""
        for requisition in self:
            user = requisition.requestor_id
            if not user._is_warehouse_allowed(requisition.dest_warehouse_id):
                raise UserError(
                    self.env._(
                        "You are not authorised to submit requisitions to '%s'. "
                        "Please select one of your assigned destination branches.",
                        requisition.dest_warehouse_id.name,
                    )
                )

    def action_submit(self):
        for requisition in self:
            if requisition.state != "draft":
                raise UserError(
                    self.env._("Only draft requisitions can be submitted.")
                )
            if not requisition.line_ids:
                raise UserError(
                    self.env._("Add at least one product before submitting.")
                )
            requisition._check_destination_authorised()
        self.write({"state": "submitted"})
        return True
```

- [ ] **Step 4: Run the test to verify it passes**

Add `from . import test_requisition_authorisation` to `tests/__init__.py`, then run.
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): enforce branch authorisation on submit (TC-STK-02)"
```

---

## Task 8: Validation, approval and internal transfer creation

**Files:**
- Modify: `addons/retail_stock_requisition/models/requisition.py`
- Create: `addons/retail_stock_requisition/models/stock_picking.py`
- Test: `addons/retail_stock_requisition/tests/test_requisition_flow.py`

**Interfaces:**
- Consumes: `action_submit()` from Task 7.
- Produces: `action_sc_validate()`, `action_finance_approve()`, `_create_internal_picking()` returning a `stock.picking` recordset, and `stock.picking.requisition_id`. Task 9 overrides `button_validate` and calls `_action_set_done()`.

- [ ] **Step 1: Write the failing test**

`addons/retail_stock_requisition/tests/test_requisition_flow.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionFlow(TransactionCase):
    """TC-STK-01: full approval flow, Westgate branch replenishment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.unga = cls.env["product.product"].create(
            {"name": "Bidii Unga Maize Flour 2kg", "type": "consu", "is_storable": True}
        )
        cls.milk = cls.env["product.product"].create(
            {"name": "Brookside Milk 500ml", "type": "consu", "is_storable": True}
        )
        cls.requisition = cls.env["retail.stock.requisition"].create(
            {
                "source_location_id": cls.central.lot_stock_id.id,
                "dest_warehouse_id": cls.westgate.id,
                "line_ids": [
                    (0, 0, {"product_id": cls.unga.id, "qty_requested": 100.0}),
                    (0, 0, {"product_id": cls.milk.id, "qty_requested": 200.0}),
                ],
            }
        )

    def test_tc_stk_01_full_approval_flow(self):
        self.requisition.action_submit()
        self.assertEqual(self.requisition.state, "submitted")

        # Supply chain trims Brookside from 200 to 150.
        milk_line = self.requisition.line_ids.filtered(
            lambda line: line.product_id == self.milk
        )
        milk_line.qty_approved = 150.0
        self.requisition.action_sc_validate()
        self.assertEqual(self.requisition.state, "sc_validated")
        self.assertEqual(self.requisition.sc_validated_by_id, self.env.user)
        self.assertTrue(self.requisition.sc_validated_date)

        self.requisition.action_finance_approve()
        self.assertEqual(self.requisition.state, "finance_approved")
        self.assertEqual(len(self.requisition.picking_ids), 1)

        picking = self.requisition.picking_ids
        self.assertEqual(picking.location_id, self.central.lot_stock_id)
        self.assertEqual(picking.location_dest_id, self.westgate.lot_stock_id)
        self.assertEqual(len(picking.move_ids), 2)

        moved_milk = picking.move_ids.filtered(
            lambda move: move.product_id == self.milk
        )
        self.assertEqual(
            moved_milk.product_uom_qty,
            150.0,
            "The transfer must carry the approved quantity, not the requested one.",
        )

    def test_approval_uses_approved_not_requested_quantity(self):
        self.requisition.action_submit()
        unga_line = self.requisition.line_ids.filtered(
            lambda line: line.product_id == self.unga
        )
        unga_line.qty_approved = 80.0
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        move = self.requisition.picking_ids.move_ids.filtered(
            lambda m: m.product_id == self.unga
        )
        self.assertEqual(move.product_uom_qty, 80.0)

    def test_zero_approved_lines_are_not_transferred(self):
        self.requisition.action_submit()
        self.requisition.line_ids.filtered(
            lambda line: line.product_id == self.milk
        ).qty_approved = 0.0
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        self.assertEqual(len(self.requisition.picking_ids.move_ids), 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_stock_requisition`.
Expected: FAIL — no attribute `action_sc_validate`.

- [ ] **Step 3: Write `models/stock_picking.py`**

```python
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    requisition_id = fields.Many2one(
        comodel_name="retail.stock.requisition",
        string="Stock Requisition",
        copy=False,
        index=True,
        ondelete="set null",
    )
```

- [ ] **Step 4: Add the approval methods to `models/requisition.py`**

```python
    def action_sc_validate(self):
        for requisition in self:
            if requisition.state != "submitted":
                raise UserError(
                    self.env._("Only submitted requisitions can be validated.")
                )
        self.write(
            {
                "state": "sc_validated",
                "sc_validated_by_id": self.env.user.id,
                "sc_validated_date": fields.Datetime.now(),
            }
        )
        return True

    def action_finance_approve(self):
        for requisition in self:
            if requisition.state != "sc_validated":
                raise UserError(
                    self.env._(
                        "Only supply-chain-validated requisitions can be approved."
                    )
                )
            requisition._create_internal_picking()
        self.write(
            {
                "state": "finance_approved",
                "finance_approved_by_id": self.env.user.id,
                "finance_approved_date": fields.Datetime.now(),
            }
        )
        return True

    def _get_internal_picking_type(self):
        """Return the internal picking type serving the source warehouse."""
        self.ensure_one()
        warehouse = self.source_location_id.warehouse_id
        picking_type = warehouse.int_type_id
        if not picking_type:
            picking_type = self.env["stock.picking.type"].search(
                [("code", "=", "internal"), ("company_id", "=", self.company_id.id)],
                limit=1,
            )
        if not picking_type:
            raise UserError(
                self.env._("No internal transfer operation type is configured.")
            )
        return picking_type

    def _create_internal_picking(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: line.qty_approved > 0)
        if not lines:
            raise UserError(
                self.env._("Approve at least one product quantity before approving.")
            )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self._get_internal_picking_type().id,
                "location_id": self.source_location_id.id,
                "location_dest_id": self.dest_location_id.id,
                "origin": self.name,
                "requisition_id": self.id,
                "scheduled_date": self.date_required or fields.Datetime.now(),
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": line.product_id.display_name,
                            "product_id": line.product_id.id,
                            "product_uom_qty": line.qty_approved,
                            "product_uom": line.product_uom_id.id,
                            "location_id": self.source_location_id.id,
                            "location_dest_id": self.dest_location_id.id,
                        },
                    )
                    for line in lines
                ],
            }
        )
        picking.action_confirm()
        return picking

    def action_view_pickings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Transfers"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("requisition_id", "=", self.id)],
        }
```

- [ ] **Step 5: Run the test to verify it passes**

Add `from . import test_requisition_flow` to `tests/__init__.py`, then run.
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): add SC validation, finance approval and transfer creation"
```

---

## Task 9: Closing the requisition on picking validation

**Files:**
- Modify: `addons/retail_stock_requisition/models/stock_picking.py`
- Modify: `addons/retail_stock_requisition/models/requisition.py`
- Test: `addons/retail_stock_requisition/tests/test_requisition_receipt.py`

**Interfaces:**
- Consumes: `stock.picking.requisition_id` from Task 8.
- Produces: `_action_set_done()` on the requisition, invoked from the `button_validate` override.

- [ ] **Step 1: Write the failing test**

`addons/retail_stock_requisition/tests/test_requisition_receipt.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionReceipt(TransactionCase):
    """US-STK-04: validating the transfer closes the requisition."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.product = cls.env["product.product"].create(
            {"name": "Dettol Antiseptic 200ml", "type": "consu", "is_storable": True}
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.central.lot_stock_id, 500.0
        )
        cls.requisition = cls.env["retail.stock.requisition"].create(
            {
                "source_location_id": cls.central.lot_stock_id.id,
                "dest_warehouse_id": cls.westgate.id,
                "line_ids": [
                    (0, 0, {"product_id": cls.product.id, "qty_requested": 40.0})
                ],
            }
        )

    def test_validating_picking_sets_requisition_done(self):
        self.requisition.action_submit()
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()

        picking = self.requisition.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertEqual(picking.state, "done")
        self.assertEqual(self.requisition.state, "done")

    def test_branch_stock_increases_by_received_quantity(self):
        self.requisition.action_submit()
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        picking = self.requisition.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        branch_qty = self.product.with_context(
            location=self.westgate.lot_stock_id.id
        ).qty_available
        self.assertEqual(branch_qty, 40.0)
        self.assertEqual(self.requisition.line_ids.qty_received, 40.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_stock_requisition`.
Expected: FAIL — requisition state stays `finance_approved`.

- [ ] **Step 3: Add `_action_set_done` to `models/requisition.py`**

```python
    def _action_set_done(self):
        """Close the requisition once every linked transfer is complete."""
        for requisition in self:
            if requisition.state != "finance_approved":
                continue
            pickings = requisition.picking_ids
            if pickings and all(
                picking.state in ("done", "cancel") for picking in pickings
            ):
                requisition.state = "done"
        return True
```

- [ ] **Step 4: Add the `button_validate` override to `models/stock_picking.py`**

```python
    def button_validate(self):
        result = super().button_validate()
        self.filtered("requisition_id").requisition_id._action_set_done()
        return result
```

Note: `button_validate` may return an action dictionary when a backorder or immediate-transfer wizard is required. The override deliberately calls `_action_set_done()` regardless, because that method itself checks whether every picking has actually reached `done`.

- [ ] **Step 5: Run the test to verify it passes**

Add `from . import test_requisition_receipt` to `tests/__init__.py`, then run.
Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): close requisition when transfer is validated"
```

---

## Task 10: Rejection wizard, reset and cancel guard

**Files:**
- Create: `addons/retail_stock_requisition/wizard/__init__.py`
- Create: `addons/retail_stock_requisition/wizard/reject_wizard.py`
- Create: `addons/retail_stock_requisition/wizard/reject_wizard_views.xml`
- Modify: `addons/retail_stock_requisition/models/requisition.py`
- Modify: `addons/retail_stock_requisition/security/ir.model.access.csv`
- Test: `addons/retail_stock_requisition/tests/test_requisition_rejection.py`, `tests/test_requisition_guards.py`

**Interfaces:**
- Consumes: the state machine from Tasks 7–8.
- Produces: `retail.requisition.reject.wizard` with field `reason` and method `action_confirm_rejection()`; `action_reject()`, `action_reset_to_draft()`, `action_cancel()` on the requisition.

- [ ] **Step 1: Write the failing tests**

`addons/retail_stock_requisition/tests/test_requisition_rejection.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionRejection(TransactionCase):
    """TC-STK-03: rejection with a reason, then resubmission."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.product = cls.env["product.product"].create(
            {"name": "Bidii Unga Maize Flour 2kg", "type": "consu", "is_storable": True}
        )
        cls.requisition = cls.env["retail.stock.requisition"].create(
            {
                "source_location_id": cls.central.lot_stock_id.id,
                "dest_warehouse_id": cls.westgate.id,
                "line_ids": [
                    (0, 0, {"product_id": cls.product.id, "qty_requested": 300.0})
                ],
            }
        )

    def _reject(self, reason):
        self.requisition.action_submit()
        wizard = (
            self.env["retail.requisition.reject.wizard"]
            .with_context(active_id=self.requisition.id)
            .create({"reason": reason})
        )
        wizard.action_confirm_rejection()

    def test_tc_stk_03_rejection_stamps_reason_and_rejector(self):
        reason = "Exceeds monthly allocation for Westgate. Reduce to 150 bags."
        self._reject(reason)
        self.assertEqual(self.requisition.state, "rejected")
        self.assertEqual(self.requisition.rejection_reason, reason)
        self.assertEqual(self.requisition.rejected_by_id, self.env.user)

    def test_tc_stk_03_reset_to_draft_clears_rejection(self):
        self._reject("Exceeds monthly allocation.")
        self.requisition.action_reset_to_draft()
        self.assertEqual(self.requisition.state, "draft")
        self.assertFalse(self.requisition.rejection_reason)
        self.assertFalse(self.requisition.rejected_by_id)

    def test_tc_stk_03_resubmission_after_revision(self):
        self._reject("Reduce to 150 bags.")
        self.requisition.action_reset_to_draft()
        self.requisition.line_ids.qty_requested = 150.0
        self.requisition.action_submit()
        self.assertEqual(self.requisition.state, "submitted")
        self.assertEqual(self.requisition.line_ids.qty_requested, 150.0)
```

`addons/retail_stock_requisition/tests/test_requisition_guards.py`:

```python
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionGuards(TransactionCase):
    """US-STK-06: cancellation is restricted to early states."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.product = cls.env["product.product"].create(
            {"name": "Royco Mchuzi Mix 200g", "type": "consu", "is_storable": True}
        )

    def _new(self):
        return self.env["retail.stock.requisition"].create(
            {
                "source_location_id": self.central.lot_stock_id.id,
                "dest_warehouse_id": self.westgate.id,
                "line_ids": [
                    (0, 0, {"product_id": self.product.id, "qty_requested": 10.0})
                ],
            }
        )

    def test_draft_can_be_cancelled(self):
        requisition = self._new()
        requisition.action_cancel()
        self.assertEqual(requisition.state, "cancelled")

    def test_submitted_can_be_cancelled(self):
        requisition = self._new()
        requisition.action_submit()
        requisition.action_cancel()
        self.assertEqual(requisition.state, "cancelled")

    def test_finance_approved_cannot_be_cancelled(self):
        requisition = self._new()
        requisition.action_submit()
        requisition.action_sc_validate()
        requisition.action_finance_approve()
        with self.assertRaises(UserError):
            requisition.action_cancel()
        self.assertEqual(requisition.state, "finance_approved")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run with `-u retail_stock_requisition`.
Expected: FAIL — model `retail.requisition.reject.wizard` does not exist.

- [ ] **Step 3: Write `wizard/reject_wizard.py`**

```python
from odoo import fields, models


class RetailRequisitionRejectWizard(models.TransientModel):
    _name = "retail.requisition.reject.wizard"
    _description = "Reject Stock Requisition"

    reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        requisition = self.env["retail.stock.requisition"].browse(
            self.env.context.get("active_id")
        )
        requisition._apply_rejection(self.reason)
        return {"type": "ir.actions.act_window_close"}
```

`addons/retail_stock_requisition/wizard/__init__.py`:

```python
from . import reject_wizard
```

- [ ] **Step 4: Add the rejection and cancel methods to `models/requisition.py`**

```python
    def action_reject(self):
        self.ensure_one()
        if self.state not in ("submitted", "sc_validated"):
            raise UserError(
                self.env._(
                    "Only submitted or validated requisitions can be rejected."
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reject Requisition"),
            "res_model": "retail.requisition.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def _apply_rejection(self, reason):
        self.ensure_one()
        self.write(
            {
                "state": "rejected",
                "rejection_reason": reason,
                "rejected_by_id": self.env.user.id,
            }
        )
        return True

    def action_reset_to_draft(self):
        for requisition in self:
            if requisition.state not in ("rejected", "cancelled"):
                raise UserError(
                    self.env._(
                        "Only rejected or cancelled requisitions can be reset to draft."
                    )
                )
        self.write(
            {
                "state": "draft",
                "rejection_reason": False,
                "rejected_by_id": False,
            }
        )
        return True

    def action_cancel(self):
        for requisition in self:
            if requisition.state not in ("draft", "submitted"):
                raise UserError(
                    self.env._(
                        "Only draft or submitted requisitions can be cancelled. "
                        "Requisition %(name)s is in state %(state)s.",
                        name=requisition.name,
                        state=requisition.state,
                    )
                )
        self.write({"state": "cancelled"})
        return True
```

- [ ] **Step 5: Write `wizard/reject_wizard_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_requisition_reject_wizard_form" model="ir.ui.view">
        <field name="name">retail.requisition.reject.wizard.form</field>
        <field name="model">retail.requisition.reject.wizard</field>
        <field name="arch" type="xml">
            <form string="Reject Requisition">
                <group>
                    <field name="reason" placeholder="State why this requisition is being rejected."/>
                </group>
                <footer>
                    <button name="action_confirm_rejection" type="object"
                            string="Confirm Rejection" class="btn-primary"/>
                    <button string="Cancel" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>
</odoo>
```

- [ ] **Step 6: Add wizard access to `security/ir.model.access.csv`**

Append these rows:

```csv
access_reject_wizard_supply_chain,reject.wizard.supply.chain,model_retail_requisition_reject_wizard,retail_base.group_supply_chain_officer,1,1,1,1
access_reject_wizard_finance,reject.wizard.finance,model_retail_requisition_reject_wizard,retail_base.group_finance_officer,1,1,1,1
```

- [ ] **Step 7: Run the tests to verify they pass**

Add both new test modules to `tests/__init__.py`, then run.
Expected: 6 tests pass.

- [ ] **Step 8: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): add rejection wizard, reset and cancel guard"
```

---

## Task 11: Email notifications

**Files:**
- Create: `addons/retail_stock_requisition/data/mail_templates.xml`
- Modify: `addons/retail_stock_requisition/models/requisition.py`
- Test: `addons/retail_stock_requisition/tests/test_requisition_notifications.py`

**Interfaces:**
- Consumes: the state transitions from Tasks 7–10.
- Produces: `_notify_role(role)` where `role` is one of `"supply_chain"`, `"finance"`, `"requestor"`.

- [ ] **Step 1: Write the failing test**

`addons/retail_stock_requisition/tests/test_requisition_notifications.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionNotifications(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.central = cls.env.ref("retail_base.warehouse_central")
        cls.westgate = cls.env.ref("retail_base.warehouse_westgate")
        cls.product = cls.env["product.product"].create(
            {"name": "Brookside Milk 500ml", "type": "consu", "is_storable": True}
        )
        cls.joseph = cls.env["res.users"].create(
            {
                "name": "Joseph Mwangi",
                "login": "joseph.notify.test",
                "email": "joseph@tano.test",
                "groups_id": [
                    (4, cls.env.ref("retail_base.group_supply_chain_officer").id)
                ],
            }
        )
        cls.requisition = cls.env["retail.stock.requisition"].create(
            {
                "source_location_id": cls.central.lot_stock_id.id,
                "dest_warehouse_id": cls.westgate.id,
                "line_ids": [
                    (0, 0, {"product_id": cls.product.id, "qty_requested": 200.0})
                ],
            }
        )

    def test_submit_posts_message_to_chatter(self):
        before = len(self.requisition.message_ids)
        self.requisition.action_submit()
        self.assertGreater(len(self.requisition.message_ids), before)

    def test_supply_chain_officer_is_notified_on_submit(self):
        self.requisition.action_submit()
        partners = self.requisition.message_ids.mapped("partner_ids")
        self.assertIn(self.joseph.partner_id, partners)
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_stock_requisition`.
Expected: FAIL — Joseph's partner is not among the notified partners.

- [ ] **Step 3: Add `_notify_role` to `models/requisition.py`**

```python
    ROLE_GROUPS = {
        "supply_chain": "retail_base.group_supply_chain_officer",
        "finance": "retail_base.group_finance_officer",
    }

    def _notify_role(self, role, body):
        """Post a chatter message notifying the users holding ``role``."""
        self.ensure_one()
        if role == "requestor":
            partners = self.requestor_id.partner_id
        else:
            group = self.env.ref(self.ROLE_GROUPS[role], raise_if_not_found=False)
            partners = group.users.partner_id if group else self.env["res.partner"]
        if not partners:
            return False
        return self.message_post(
            body=body,
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_comment",
        )
```

- [ ] **Step 4: Wire the notifications into the transitions**

In `action_submit`, after `self.write({"state": "submitted"})`:

```python
        for requisition in self:
            requisition._notify_role(
                "supply_chain",
                self.env._(
                    "Requisition %(name)s for %(branch)s awaits supply chain validation.",
                    name=requisition.name,
                    branch=requisition.dest_warehouse_id.name,
                ),
            )
```

In `action_sc_validate`, after the write:

```python
        for requisition in self:
            requisition._notify_role(
                "finance",
                self.env._(
                    "Requisition %(name)s has been validated and awaits finance approval.",
                    name=requisition.name,
                ),
            )
```

In `action_finance_approve`, after the write:

```python
        for requisition in self:
            requisition._notify_role(
                "requestor",
                self.env._(
                    "Transfer in progress for %(branch)s against requisition %(name)s.",
                    branch=requisition.dest_warehouse_id.name,
                    name=requisition.name,
                ),
            )
```

In `_apply_rejection`, after the write:

```python
        self._notify_role(
            "requestor",
            self.env._(
                "Requisition %(name)s was rejected: %(reason)s",
                name=self.name,
                reason=reason,
            ),
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Add `from . import test_requisition_notifications` to `tests/__init__.py`, then run.
Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): notify supply chain, finance and requestor"
```

---

## Task 12: Views, menus and record rules

**Files:**
- Create: `addons/retail_stock_requisition/views/requisition_views.xml`
- Create: `addons/retail_stock_requisition/views/menus.xml`
- Create: `addons/retail_stock_requisition/security/requisition_groups.xml`
- Test: `addons/retail_stock_requisition/tests/test_requisition_views.py`

**Interfaces:**
- Consumes: every action method from Tasks 7–11.
- Produces: action `retail_stock_requisition.action_retail_stock_requisition` and the record rule `rule_requisition_own_branches`.

- [ ] **Step 1: Write the failing test**

`addons/retail_stock_requisition/tests/test_requisition_views.py`:

```python
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRequisitionViews(TransactionCase):

    def test_views_render(self):
        """Every view arch must validate against the model."""
        for view_type in ("form", "list", "search"):
            arch = self.env["retail.stock.requisition"].get_view(view_type=view_type)
            self.assertTrue(arch.get("arch"))

    def test_action_exists(self):
        action = self.env.ref(
            "retail_stock_requisition.action_retail_stock_requisition"
        )
        self.assertEqual(action.res_model, "retail.stock.requisition")

    def test_record_rule_exists(self):
        rule = self.env.ref(
            "retail_stock_requisition.rule_requisition_own_branches",
            raise_if_not_found=False,
        )
        self.assertTrue(rule)
```

- [ ] **Step 2: Run the test to verify it fails**

Run with `-u retail_stock_requisition`.
Expected: FAIL — action reference not found.

- [ ] **Step 3: Write `views/requisition_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_retail_stock_requisition_form" model="ir.ui.view">
        <field name="name">retail.stock.requisition.form</field>
        <field name="model">retail.stock.requisition</field>
        <field name="arch" type="xml">
            <form string="Stock Requisition">
                <header>
                    <button name="action_submit" type="object" string="Submit"
                            class="btn-primary" invisible="state != 'draft'"/>
                    <button name="action_sc_validate" type="object" string="SC Validate"
                            class="btn-primary" invisible="state != 'submitted'"
                            groups="retail_base.group_supply_chain_officer"/>
                    <button name="action_finance_approve" type="object"
                            string="Finance Approve" class="btn-primary"
                            invisible="state != 'sc_validated'"
                            groups="retail_base.group_finance_officer"/>
                    <button name="action_reject" type="object" string="Reject"
                            invisible="state not in ('submitted', 'sc_validated')"/>
                    <button name="action_cancel" type="object" string="Cancel"
                            invisible="state not in ('draft', 'submitted')"/>
                    <button name="action_reset_to_draft" type="object"
                            string="Reset to Draft"
                            invisible="state not in ('rejected', 'cancelled')"/>
                    <field name="state" widget="statusbar"
                           statusbar_visible="draft,submitted,sc_validated,finance_approved,done"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="action_view_pickings" type="object"
                                class="oe_stat_button" icon="fa-truck"
                                invisible="picking_count == 0">
                            <field name="picking_count" widget="statinfo" string="Transfers"/>
                        </button>
                    </div>
                    <div class="oe_title">
                        <h1><field name="name" readonly="1"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="requestor_id" readonly="state != 'draft'"/>
                            <field name="source_location_id" readonly="state != 'draft'"/>
                            <field name="dest_warehouse_id" readonly="state != 'draft'"/>
                        </group>
                        <group>
                            <field name="date_required" readonly="state != 'draft'"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                            <field name="sc_validated_by_id" invisible="not sc_validated_by_id"/>
                            <field name="finance_approved_by_id" invisible="not finance_approved_by_id"/>
                        </group>
                    </group>
                    <div class="alert alert-warning" role="alert" invisible="state != 'rejected'">
                        <strong>Rejected by <field name="rejected_by_id" readonly="1" nolabel="1"/>:</strong>
                        <field name="rejection_reason" readonly="1" nolabel="1"/>
                    </div>
                    <notebook>
                        <page string="Products" name="products">
                            <field name="line_ids" readonly="state in ('done', 'cancelled', 'rejected')">
                                <list editable="bottom">
                                    <field name="product_id"/>
                                    <field name="qty_requested"/>
                                    <field name="qty_available_source" readonly="1"
                                           string="Available"/>
                                    <field name="qty_approved"/>
                                    <field name="qty_received" readonly="1"/>
                                    <field name="product_uom_id" readonly="1"/>
                                </list>
                            </field>
                        </page>
                    </notebook>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>

    <record id="view_retail_stock_requisition_list" model="ir.ui.view">
        <field name="name">retail.stock.requisition.list</field>
        <field name="model">retail.stock.requisition</field>
        <field name="arch" type="xml">
            <list string="Stock Requisitions">
                <field name="name"/>
                <field name="requestor_id"/>
                <field name="dest_warehouse_id"/>
                <field name="date_required"/>
                <field name="state" widget="badge"
                       decoration-success="state == 'done'"
                       decoration-danger="state == 'rejected'"
                       decoration-info="state == 'submitted'"/>
            </list>
        </field>
    </record>

    <record id="view_retail_stock_requisition_search" model="ir.ui.view">
        <field name="name">retail.stock.requisition.search</field>
        <field name="model">retail.stock.requisition</field>
        <field name="arch" type="xml">
            <search string="Stock Requisitions">
                <field name="name"/>
                <field name="requestor_id"/>
                <field name="dest_warehouse_id"/>
                <filter name="filter_draft" string="Draft" domain="[('state', '=', 'draft')]"/>
                <filter name="filter_submitted" string="Submitted" domain="[('state', '=', 'submitted')]"/>
                <filter name="filter_sc_validated" string="SC Validated" domain="[('state', '=', 'sc_validated')]"/>
                <filter name="filter_approved" string="Finance Approved" domain="[('state', '=', 'finance_approved')]"/>
                <group expand="0" string="Group By">
                    <filter name="group_branch" string="Branch" context="{'group_by': 'dest_warehouse_id'}"/>
                    <filter name="group_state" string="Status" context="{'group_by': 'state'}"/>
                </group>
            </search>
        </field>
    </record>

    <record id="action_retail_stock_requisition" model="ir.actions.act_window">
        <field name="name">Stock Requisitions</field>
        <field name="res_model">retail.stock.requisition</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="view_retail_stock_requisition_search"/>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Raise a stock requisition</p>
            <p>Request replenishment from the central warehouse to your branch.</p>
        </field>
    </record>
</odoo>
```

- [ ] **Step 4: Write `views/menus.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_retail_requisition_root"
              name="Stock Requisitions"
              parent="stock.menu_stock_root"
              sequence="15"/>
    <menuitem id="menu_retail_requisition_all"
              name="Requisitions"
              parent="menu_retail_requisition_root"
              action="action_retail_stock_requisition"
              sequence="10"/>
</odoo>
```

- [ ] **Step 5: Write `security/requisition_groups.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="rule_requisition_own_branches" model="ir.rule">
        <field name="name">Requisitions: own branches only</field>
        <field name="model_id" ref="model_retail_stock_requisition"/>
        <field name="domain_force">
            ['|', ('requestor_id', '=', user.id),
                  ('dest_warehouse_id', 'in', user.retail_warehouse_ids.ids)]
        </field>
        <field name="groups" eval="[(4, ref('point_of_sale.group_pos_manager'))]"/>
    </record>

    <record id="rule_requisition_head_office" model="ir.rule">
        <field name="name">Requisitions: head office sees all</field>
        <field name="model_id" ref="model_retail_stock_requisition"/>
        <field name="domain_force">[(1, '=', 1)]</field>
        <field name="groups" eval="[
            (4, ref('retail_base.group_supply_chain_officer')),
            (4, ref('retail_base.group_finance_officer'))
        ]"/>
    </record>
</odoo>
```

- [ ] **Step 6: Run the test to verify it passes**

Add `from . import test_requisition_views` to `tests/__init__.py`, then run the full module suite.
Expected: all Phase 1 tests pass.

- [ ] **Step 7: Commit**

```bash
git add addons/retail_stock_requisition
git commit -m "feat(requisition): add views, menus and record rules"
```

---

## Task 13: Full-suite verification and README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–12.
- Produces: verified evidence that Phase 1 is complete.

- [ ] **Step 1: Run the complete Phase 1 suite on a fresh database**

```bash
C:/Users/orega/odoo18-dev/pgsql/bin/dropdb.exe -p 5433 -U odoo --if-exists tano_verify
C:/Users/orega/odoo18-dev/venv/Scripts/python.exe C:/Users/orega/odoo18-dev/odoo18/odoo-bin \
  -c config/odoo.conf -d tano_verify \
  -i retail_base,retail_stock_requisition \
  --test-enable --stop-after-init
```

Expected: `0 failed, 0 error(s)` in the log tail. Record the actual counts.

- [ ] **Step 2: Write `README.md`**

Document: what the project is, the runtime setup commands from Task 1, how to run the tests, the module list, and a pointer to the spec and this plan.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add project README and Phase 1 verification notes"
```

---

## Phase 1 Definition of Done

- [ ] `retail_base` and `retail_stock_requisition` install cleanly on a fresh Odoo 18 CE database
- [ ] TC-STK-01, TC-STK-02 and TC-STK-03 pass as named tests
- [ ] A finance-approved requisition creates a real internal transfer carrying approved quantities
- [ ] Validating that transfer moves the requisition to `done` and increases branch stock
- [ ] Cancelling a finance-approved requisition raises `UserError`
- [ ] Full suite reports zero failures and zero errors
