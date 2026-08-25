import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

/**
 * Refuse to add an out-of-stock storable product to the cart.
 *
 * Availability is asked for on demand rather than shipped with the session
 * payload: qty_available is a computed field, so loading it for a
 * supermarket's whole catalogue would be expensive to answer a question about
 * the few products actually scanned. Answers are cached for the session so a
 * repeatedly scanned item costs one round trip, and the cache is invalidated
 * for a product once it is successfully added.
 */
patch(PosStore.prototype, {
    /**
     * @returns {Map<number, number>} product id to known available quantity
     */
    get retailStockCache() {
        if (!this._retailStockCache) {
            this._retailStockCache = new Map();
        }
        return this._retailStockCache;
    },

    async retailIsProductAvailable(product) {
        if (!this.config.retail_block_zero_qty) {
            return true;
        }
        // Only storable products have a stock figure worth checking.
        if (!product || product.is_storable === false) {
            return true;
        }

        if (this.retailStockCache.has(product.id)) {
            return this.retailStockCache.get(product.id) > 0;
        }

        let available = true;
        try {
            available = await this.data.call(
                "product.product",
                "is_retail_available",
                [product.id, this.config.id]
            );
        } catch {
            // A till that cannot reach the server must keep trading. Failing
            // open is deliberate: blocking every sale during a network blip
            // would be worse than briefly overselling.
            return true;
        }
        this.retailStockCache.set(product.id, available ? 1 : 0);
        return available;
    },

    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        let product = vals.product_id;
        if (typeof product === "number") {
            product = this.data.models["product.product"].get(product);
        }

        const available = await this.retailIsProductAvailable(product);
        if (!available) {
            this.dialog.add(AlertDialog, {
                title: _t("Out of stock"),
                body: _t(
                    "%s is out of stock and cannot be added to the cart. " +
                        "Offer the customer an alternative.",
                    product?.display_name || _t("This product")
                ),
            });
            return false;
        }

        const line = await super.addLineToCurrentOrder(vals, opts, configure);
        // The cached figure is now stale for this product.
        this.retailStockCache.delete(product?.id);
        return line;
    },
});
