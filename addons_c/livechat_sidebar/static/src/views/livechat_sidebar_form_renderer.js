/** @odoo-module **/

import { Discuss } from "@mail/core/public_web/discuss";
import { LivechatSessionList } from "./livechat_session_list";
import { NewChatDialog } from "./new_chat_dialog";

import { onMounted, onPatched, onWillStart, onWillUnmount, onWillUpdateProps, useEffect, useRef, useState } from "@odoo/owl";

import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { FormRenderer } from "@web/views/form/form_renderer";

export class LivechatSidebarFormRenderer extends FormRenderer {
    static template = "livechat_sidebar.LivechatSidebarDiscuss";
    static components = {
        ...FormRenderer.components,
        Discuss,
        LivechatSessionList,
    };

    setup() {
        super.setup();
        this.store = useState(useService("mail.store"));
        this.action = useService("action");
        this.dialogService = useService("dialog");
        this.busService = useService("bus_service");
        this.notificationService = useService("notification");
        this.mainContentRef = useRef("mainContent");
        this.state = useState({
            sessions: [],
            loading: true,
            searchQuery: "",
            friendRequest: {
                visible: true,
                loading: false,
                sent: false,
                error: "",
            },
        });
        this._debouncedLoadSessions = useDebounced(() => this.loadSessions(), 500);
        this._onNewMessage = () => this._debouncedLoadSessions();
        this._onChannelChanged = () => this._debouncedLoadSessions();
        useEffect(
            (thread) => {
                if (thread) {
                    thread.shadowedBySelf++;
                    return () => thread.shadowedBySelf--;
                }
            },
            () => [this.thread]
        );
        onWillStart(async () => {
            await this.getChannel(this.props);
            await this.loadSessions();
        });
        onWillUpdateProps(async (nextProps) => {
            if (nextProps.record.resId !== this.props.record.resId) {
                await this.getChannel(nextProps);
                this.state.friendRequest.visible = true;
                this.state.friendRequest.sent = false;
                this.state.friendRequest.error = "";
                this.state.friendRequest.loading = false;
            }
            await this.loadSessions();
        });
        onMounted(() => {
            this._previousDiscussIsActive = this.store.discuss.isActive;
            this.store.discuss.isActive = true;
            this.busService.subscribe("discuss.channel/new_message", this._onNewMessage);
            this.busService.subscribe("mail.record/insert", this._onChannelChanged);
            this._moveFriendRequestToHeader();
        });
        onPatched(() => {
            this._moveFriendRequestToHeader();
        });
        onWillUnmount(() => {
            this.store.discuss.isActive = this._previousDiscussIsActive;
            this.busService.unsubscribe("discuss.channel/new_message", this._onNewMessage);
            this.busService.unsubscribe("mail.record/insert", this._onChannelChanged);
        });
    }

    _moveFriendRequestToHeader() {
        const el = this.mainContentRef.el;
        if (!el) return;
        const frEl = el.querySelector(".o_friend_request_header");
        const header = el.querySelector(".o-mail-DiscussContent-header");
        if (frEl && header && frEl.parentElement !== header) {
            header.appendChild(frEl);
        }
        if (frEl) {
            frEl.classList.remove("d-none");
        }
    }

    async getChannel(props) {
        this.thread = await this.store.Thread.getOrFetch({
            model: "discuss.channel",
            id: props.record.resId,
        });
    }

    async loadSessions() {
        try {
            const sessions = await rpc("/livechat_sidebar/get_sessions", {
                current_channel_id: this.props.record.resId,
                search_query: this.state.searchQuery || "",
            });
            this.state.sessions = sessions;
        } catch (e) {
            console.error("Failed to load sessions", e);
            this.state.sessions = [];
        }
        this.state.loading = false;
    }

    onSearchInput(value) {
        this.state.searchQuery = value;
        this.loadSessions();
    }

    async onSessionClick(sessionId) {
        if (sessionId === this.props.record.resId) {
            return;
        }
        const action = await this.action.loadAction("livechat_sidebar.livechat_sidebar_chat_action");
        action.res_id = sessionId;
        action.views = [[false, "form"]];
        action.view_mode = "form";
        action.context = { form_view_ref: "im_livechat.discuss_channel_view_form" };
        this.action.doAction(action, {
            clearBreadcrumbs: true,
        });
    }

    redirectToSessions() {
        this.action.doAction("im_livechat.discuss_channel_action", {
            clearBreadcrumbs: true,
        });
    }

    get currentChannelPhone() {
        const session = this.state.sessions.find(s => s.id === this.props.record.resId);
        if (session) {
            if (session.visitor_phone) return session.visitor_phone;
            const name = session.visitor_name || session.name || "";
            const match = name.match(/\d{9,15}/);
            if (match) return match[0];
        }
        return "";
    }

    async sendFriendRequest() {
        const phone = this.currentChannelPhone;
        if (!phone) {
            this.notificationService.add("Không tìm thấy số điện thoại cho session này.", { type: "warning" });
            return;
        }
        this.state.friendRequest.loading = true;
        this.state.friendRequest.error = "";
        try {
            const result = await rpc("/livechat_sidebar/zalo_send_friend_request", { phone });
            if (result.success) {
                this.state.friendRequest.sent = true;
                this.notificationService.add("Đã gửi lời mời kết bạn Zalo thành công!", { type: "success" });
            } else {
                this.state.friendRequest.error = result.error || "Gửi lời mời thất bại.";
            }
        } catch (e) {
            this.state.friendRequest.error = e.message || "Lỗi kết nối.";
        }
        this.state.friendRequest.loading = false;
    }

    dismissFriendRequest() {
        this.state.friendRequest.visible = false;
    }

    onNewChat() {
        this.dialogService.add(NewChatDialog, {
            onConfirm: async (phone) => {
                const result = await rpc("/livechat_sidebar/create_session", { phone });
                if (result.error) {
                    throw new Error(result.error);
                }
                if (result.existing) {
                    this.notificationService.add(
                        "Đã tồn tại cuộc trò chuyện đang mở với số điện thoại này.",
                        { type: "info" }
                    );
                }
                await this.loadSessions();
                await this.onSessionClick(result.channel_id);
            },
        });
    }
}
