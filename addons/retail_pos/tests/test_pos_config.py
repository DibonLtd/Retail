from odoo.tests import tagged

from .common import RetailPosCase


@tagged("post_install", "-at_install")
class TestPosConfig(RetailPosCase):

    def test_block_zero_qty_defaults_on(self):
        """Blocking is the safe default: do not sell stock the branch lacks."""
        self.assertTrue(self.config.retail_block_zero_qty)

    def test_return_window_defaults_to_seven_days(self):
        self.assertEqual(self.config.retail_return_window_days, 7)

    def test_config_fields_reach_the_pos_front_end(self):
        """The OWL guard reads these off this.config, so they must be loaded.

        pos.config inherits pos.load.mixin, whose _load_pos_data_fields
        returns an empty list, and search_read with no field list returns
        every field. This test pins that behaviour: if Odoo ever narrows it
        to an explicit list, the guard would silently stop working.
        """
        fields_loaded = self.env["pos.config"]._load_pos_data_fields(self.config.id)
        if fields_loaded:
            self.assertIn("retail_block_zero_qty", fields_loaded)
        else:
            data = self.config.search_read([("id", "=", self.config.id)], [], load=False)
            self.assertIn("retail_block_zero_qty", data[0])
            self.assertIn("retail_return_window_days", data[0])
