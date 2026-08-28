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
