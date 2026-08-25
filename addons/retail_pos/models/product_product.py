from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def get_retail_availability(self, product_ids, config_id):
        """Return ``{product_id: qty_available}`` for the till's warehouse.

        Deliberately an on-demand call rather than a field shipped with the
        POS session payload. ``qty_available`` is computed, not stored, so
        loading it for a supermarket's full catalogue would cost a great deal
        at session open to answer a question about the handful of products
        actually scanned.
        """
        config = self.env["pos.config"].browse(config_id)
        products = self.browse(product_ids).exists()
        warehouse = config.warehouse_id
        if warehouse:
            products = products.with_context(warehouse_id=warehouse.id)
        return {
            product.id: product.qty_available
            for product in products
        }

    @api.model
    def is_retail_available(self, product_id, config_id):
        """True when the product may be sold at this till.

        Non-storable products (services, consumables not tracked) are always
        available: there is no stock figure to check.
        """
        product = self.browse(product_id).exists()
        if not product:
            return False
        if not product.is_storable:
            return True
        config = self.env["pos.config"].browse(config_id)
        if not config.retail_block_zero_qty:
            return True
        availability = self.get_retail_availability([product.id], config_id)
        return availability.get(product.id, 0.0) > 0
