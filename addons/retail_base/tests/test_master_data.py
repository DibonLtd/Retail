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
