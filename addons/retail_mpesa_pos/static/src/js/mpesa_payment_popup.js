import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// How long to keep polling an STK push before giving up, in milliseconds.
// Safaricom times a prompt out after about a minute.
const POLL_INTERVAL = 3000;
const POLL_TIMEOUT = 75000;

/**
 * Captures an M-PESA payment at the till.
 *
 * Two routes, both needed:
 *  - STK push: the cashier types the customer's number and Odoo pushes a
 *    prompt to their phone, then polls for the outcome.
 *  - Manual reference: the customer already paid the till from their own
 *    handset and reads out the confirmation code. This is how most Kenyan
 *    till payments actually happen, so it is a first-class path, not a
 *    fallback.
 */
export class MpesaPaymentPopup extends Component {
    static template = "retail_mpesa_pos.MpesaPaymentPopup";
    static components = { Dialog };
    static props = {
        amount: Number,
        reference: String,
        paymentMethodId: Number,
        allowStk: { type: Boolean, optional: true },
        data: Object,
        getPayload: Function,
        close: Function,
    };
    static defaultProps = { allowStk: true };

    setup() {
        this.state = useState({
            mode: this.props.allowStk ? "stk" : "manual",
            phone: "",
            receipt: "",
            status: "idle", // idle | pushing | waiting | done | error
            message: "",
        });
        this._cancelled = false;
    }

    get canSubmit() {
        if (this.state.status === "pushing" || this.state.status === "waiting") {
            return false;
        }
        return this.state.mode === "stk"
            ? this.state.phone.replace(/\D/g, "").length >= 9
            : this.state.receipt.trim().length > 0;
    }

    setMode(mode) {
        this.state.mode = mode;
        this.state.status = "idle";
        this.state.message = "";
    }

    async confirm() {
        if (!this.canSubmit) {
            return;
        }
        if (this.state.mode === "manual") {
            await this.recordManual();
        } else {
            await this.pushAndWait();
        }
    }

    async recordManual() {
        this.state.status = "pushing";
        this.state.message = _t("Recording payment...");
        try {
            const result = await this.props.data.call(
                "pos.payment.method",
                "retail_mpesa_record_manual",
                [
                    [this.props.paymentMethodId],
                    this.state.receipt,
                    this.props.amount,
                    this.props.reference,
                ]
            );
            this.finish(result.receipt_number);
        } catch (error) {
            this.fail(error);
        }
    }

    async pushAndWait() {
        this.state.status = "pushing";
        this.state.message = _t("Sending prompt to the customer's phone...");
        let pushed;
        try {
            pushed = await this.props.data.call(
                "pos.payment.method",
                "retail_mpesa_stk_push",
                [
                    [this.props.paymentMethodId],
                    this.state.phone,
                    this.props.amount,
                    this.props.reference,
                ]
            );
        } catch (error) {
            this.fail(error);
            return;
        }

        this.state.status = "waiting";
        this.state.message = _t("Waiting for the customer to enter their PIN...");

        const deadline = POLL_TIMEOUT / POLL_INTERVAL;
        for (let attempt = 0; attempt < deadline; attempt++) {
            await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL));
            if (this._cancelled) {
                return;
            }
            let polled;
            try {
                polled = await this.props.data.call(
                    "pos.payment.method",
                    "retail_mpesa_poll",
                    [[this.props.paymentMethodId], pushed.checkout_request_id]
                );
            } catch {
                // A transient failure while polling is not a failed payment;
                // keep waiting rather than telling the cashier it failed.
                continue;
            }
            if (polled.state === "success") {
                this.finish(polled.receipt_number);
                return;
            }
            if (["failed", "cancelled", "timeout"].includes(polled.state)) {
                this.state.status = "error";
                this.state.message =
                    polled.result_description ||
                    _t("The customer did not complete the payment.");
                return;
            }
        }

        // Timed out on our side. The payment may still land, so offer manual
        // entry rather than declaring failure.
        this.state.status = "error";
        this.state.message = _t(
            "No confirmation yet. If the customer received the money request " +
                "and paid, enter the confirmation code manually."
        );
        this.state.mode = "manual";
    }

    finish(receiptNumber) {
        this.state.status = "done";
        this.props.getPayload({ receipt_number: receiptNumber });
        this.props.close();
    }

    fail(error) {
        this.state.status = "error";
        this.state.message =
            error?.data?.message || error?.message || _t("The payment could not be recorded.");
    }

    cancel() {
        this._cancelled = true;
        this.props.close();
    }
}
