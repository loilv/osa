/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Mask a phone number: show first 3 chars and last 3 chars, replace middle with ****
 * e.g. 0987654321 -> 098****321
 */
function maskPhone(phone) {
    if (!phone) return "";
    const cleaned = phone.replace(/\s+/g, "");
    if (cleaned.length <= 6) return cleaned;
    const head = cleaned.slice(0, 3);
    const tail = cleaned.slice(-3);
    const mid = "*".repeat(Math.min(cleaned.length - 6, 4));
    return head + mid + tail;
}

export class AsteriskPhoneField extends Component {
    static template = "asterisk_connector.AsteriskPhoneField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
    };

    setup() {
        this.inputHook = useInputField({ getValue: () => this.props.record.data[this.props.name] || "" });

        // Try to get phone service; gracefully handle if not available
        try {
            this.phoneService = useService("asterisk_phone");
        } catch {
            this.phoneService = null;
        }
    }

    get phoneValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get maskedPhone() {
        return maskPhone(this.phoneValue);
    }

    get phoneHref() {
        return "tel:" + this.phoneValue.replace(/\s+/g, "");
    }

    async onCallClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const phone = this.phoneValue;
        if (!phone) return;

        if (this.phoneService) {
            await this.phoneService.makeCall(phone);
        } else {
            window.location.href = "tel:" + phone.replace(/\s+/g, "");
        }
    }
}

export const asteriskPhoneField = {
    component: AsteriskPhoneField,
    displayName: _t("Phone (Asterisk)"),
    supportedTypes: ["char"],
    extractProps: ({ placeholder }) => ({ placeholder }),
};

registry.category("fields").add("asterisk_phone", asteriskPhoneField);
