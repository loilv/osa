/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

export class NewChatDialog extends Component {
    static template = "livechat_sidebar.NewChatDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onConfirm: Function,
    };

    setup() {
        this.state = useState({
            phone: "",
            error: "",
            loading: false,
            zaloLoading: false,
            zaloInfo: null,
            zaloError: "",
        });
    }

    onPhoneInput(ev) {
        this.state.phone = ev.target.value;
        this.state.error = "";
        this.state.zaloInfo = null;
        this.state.zaloError = "";
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.onConfirm();
        }
    }

    async onFetchZaloInfo() {
        const phone = this.state.phone.trim();
        if (!phone) {
            this.state.zaloError = _t("Please enter a phone number first.");
            return;
        }
        this.state.zaloLoading = true;
        this.state.zaloInfo = null;
        this.state.zaloError = "";
        try {
            const result = await rpc("/livechat_sidebar/zalo_get_user_info", { phone });
            if (result.success) {
                this.state.zaloInfo = result.data;
            } else {
                this.state.zaloError = result.error || _t("Could not find Zalo user.");
            }
        } catch (e) {
            this.state.zaloError = e.message || _t("Failed to fetch Zalo info.");
        }
        this.state.zaloLoading = false;
    }

    async onConfirm() {
        const phone = this.state.phone.trim();
        if (!phone) {
            this.state.error = _t("Please enter a phone number.");
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            await this.props.onConfirm(phone);
            this.props.close();
        } catch (e) {
            this.state.error = e.message || _t("Failed to create conversation.");
            this.state.loading = false;
        }
    }
}
