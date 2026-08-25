from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionViews(RequisitionCase):

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

    def test_transfers_action_filters_by_requisition(self):
        requisition = self._new_requisition(lines=[(self.royco, 5.0)])
        requisition.action_submit()
        requisition.action_sc_validate()
        requisition.action_finance_approve()
        action = requisition.action_view_pickings()
        self.assertEqual(action["res_model"], "stock.picking")
        self.assertIn(("requisition_id", "=", requisition.id), action["domain"])
