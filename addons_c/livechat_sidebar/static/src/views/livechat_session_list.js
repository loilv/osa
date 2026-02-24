/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class LivechatSessionList extends Component {
    static template = "livechat_sidebar.LivechatSessionList";
    static props = {
        sessions: { type: Array },
        loading: { type: Boolean },
        currentSessionId: { type: Number, optional: true },
        onSessionClick: { type: Function },
        onSearchInput: { type: Function },
        onNewChat: { type: Function },
        searchQuery: { type: String, optional: true },
    };

    getStatusIcon(session) {
        if (session.is_closed) {
            return "text-muted";
        }
        switch (session.livechat_status) {
            case "in_progress":
                return "text-success";
            case "waiting":
                return "text-warning";
            case "need_help":
                return "text-danger";
            default:
                return "text-muted";
        }
    }

    getStatusLabel(session) {
        if (session.is_closed) {
            return "Closed";
        }
        switch (session.livechat_status) {
            case "in_progress":
                return "In progress";
            case "waiting":
                return "Waiting";
            case "need_help":
                return "Need help";
            default:
                return "";
        }
    }

    formatTime(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        if (diffMins < 1) return "Now";
        if (diffMins < 60) return `${diffMins}m`;
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}h`;
        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 7) return `${diffDays}d`;
        return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }

    truncate(text, maxLen = 40) {
        if (!text) return "";
        return text.length > maxLen ? text.substring(0, maxLen) + "..." : text;
    }

    onSearchChange(ev) {
        this.props.onSearchInput(ev.target.value);
    }

    onNewChatClick() {
        this.props.onNewChat();
    }
}
