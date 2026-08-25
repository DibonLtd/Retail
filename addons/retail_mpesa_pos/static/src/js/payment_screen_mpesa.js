import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { MpesaPaymentPopup } from "./mpesa_payment_popup";

/**
 * When the cashier picks an M-PESA method, capture the confirmation code
 * before the payment line is accepted, so no M-PESA line can exist without a
 * traceable reference.
 */
patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        const isMpesa = Boolean(paymentMethod.retail_mpesa_config_id);
        if (!isMpesa) {
            return super.addNewPaymentLine(...arguments);
        }

        const order = this.currentOrder;
        const due = order.get_due();
        const payload = await makeAwaitable(this.dialog, MpesaPaymentPopup, {
            amount: due,
            reference: order.name || "",
            paymentMethodId: paymentMethod.id,
            allowStk: paymentMethod.retail_mpesa_allow_stk !== false,
            data: this.pos.data,
        });

        if (!payload || !payload.receipt_number) {
            // Cashier cancelled, or the payment never confirmed. Adding no
            // line is correct: an unreferenced M-PESA line would be
            // untraceable against the Safaricom settlement report.
            return false;
        }

        const added = await super.addNewPaymentLine(...arguments);
        const line = this.selectedPaymentLine;
        if (line) {
            line.retail_mpesa_receipt = payload.receipt_number;
        }
        return added;
    },
});
