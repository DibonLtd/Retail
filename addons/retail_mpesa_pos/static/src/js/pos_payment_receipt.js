import { patch } from "@web/core/utils/patch";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";

/**
 * Put the M-PESA confirmation code on the printed receipt (US-POS-04).
 *
 * The reference rides through the payment line that the standard receipt
 * template already renders, rather than through a template override. A
 * customer disputing a payment, and a finance officer reconciling against the
 * Safaricom settlement report, both work from this code, so it has to be on
 * the paper the customer walks away with.
 */
patch(PosPayment.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        if (this.retail_mpesa_receipt) {
            result.name = `${result.name} — Ref: ${this.retail_mpesa_receipt}`;
        }
        return result;
    },
});
