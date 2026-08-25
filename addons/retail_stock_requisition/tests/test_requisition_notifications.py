from odoo.tests import tagged

from .common import RequisitionCase


@tagged("post_install", "-at_install")
class TestRequisitionNotifications(RequisitionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        cls.margaret = cls.env["res.users"].create(
            {
                "name": "Margaret Otieno",
                "login": "margaret.notify.test",
                "email": "margaret@tano.test",
                "groups_id": [
                    (4, cls.env.ref("retail_base.group_finance_officer").id)
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.requisition = self._new_requisition(lines=[(self.milk, 200.0)])

    def test_submit_posts_message_to_chatter(self):
        before = len(self.requisition.message_ids)
        self.requisition.action_submit()
        self.assertGreater(len(self.requisition.message_ids), before)

    def test_supply_chain_officer_is_notified_on_submit(self):
        self.requisition.action_submit()
        partners = self.requisition.message_ids.mapped("partner_ids")
        self.assertIn(self.joseph.partner_id, partners)

    def test_finance_officer_is_notified_on_sc_validation(self):
        self.requisition.action_submit()
        self.requisition.action_sc_validate()
        partners = self.requisition.message_ids.mapped("partner_ids")
        self.assertIn(self.margaret.partner_id, partners)

    def test_requestor_is_notified_on_finance_approval(self):
        self.requisition.action_submit()
        self.requisition.action_sc_validate()
        self.requisition.action_finance_approve()
        partners = self.requisition.message_ids.mapped("partner_ids")
        self.assertIn(self.requisition.requestor_id.partner_id, partners)
