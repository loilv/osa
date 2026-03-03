/** @odoo-module **/

import { ChatWindow } from "@mail/core/common/chat_window_model";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

// Track channel IDs opened from Zalo wizard
const zaloOpenedChannels = new Set();

/**
 * Patch ChatWindow so that closing a Zalo-opened livechat window
 * just hides the UI without ending the livechat session.
 */
patch(ChatWindow.prototype, {
    close(options = {}) {
        return super.close({ ...options, force: true, notifyState: false });
    },
});

/**
 * Service that listens for bus notifications to open a ChatWindow.
 * Triggered by zalo.chat.wizard's action_open_chat via bus.bus._sendone().
 */
const telesaleCrmService = {
    dependencies: ["bus_service", "mail.store"],
    start(env, services) {
        const busService = services.bus_service;
        const store = services["mail.store"];

        // Listen for open chat window notifications
        busService.subscribe("telesale_crm/open_chat_window", async (payload) => {
            const channelId = payload.channel_id;
            if (!channelId) return;
            zaloOpenedChannels.add(channelId);
            const thread = await store.Thread.getOrFetch({
                model: "discuss.channel",
                id: channelId,
            });
            if (thread) {
                thread.openChatWindow({ focus: true });
            }
        });

        // Listen for make call notifications — use asterisk_phone service
        busService.subscribe("telesale_crm/make_call", async (payload) => {
            const phone = payload.phone;
            if (!phone) return;
            try {
                const phoneService = env.services["asterisk_phone"];
                if (phoneService) {
                    await phoneService.makeCall(phone);
                } else {
                    window.location.href = "tel:" + phone.replace(/\s+/g, "");
                }
            } catch (e) {
                console.error("[telesale_crm] makeCall error:", e);
                window.location.href = "tel:" + phone.replace(/\s+/g, "");
            }
        });
    },
};

registry.category("services").add("telesale_crm.service", telesaleCrmService);
