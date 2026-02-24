/** @odoo-module **/

import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    /**
     * Override rename to support livechat channels.
     * The original rename() skips livechat because isChatChannel only includes
     * "chat" and "group". We add livechat support by calling channel_rename
     * to update discuss.channel.name in the database.
     */
    async rename(name) {
        const newName = name.trim();
        if (this.channel_type === "livechat" && newName && newName !== this.displayName) {
            this.name = newName;
            await this.store.env.services.orm.call(
                "discuss.channel",
                "channel_rename",
                [[this.id]],
                { name: newName }
            );
        }
        return super.rename(name);
    },
});
