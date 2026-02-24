/** @odoo-module **/

import { Component, useState, onMounted, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

// Shared events
const SHOW_HOME_EVENT = "telesale_show_home";

// ============================================================
// TelesaleMenu - Full-screen grid home menu
// ============================================================
export class TelesaleMenu extends Component {
    static template = "telesale_menu.TelesaleMenu";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.menuService = useService("menu");

        this.state = useState({
            apps: [],
            searchQuery: "",
            isVisible: false,
            isEnabled: true,
        });

        this._onShowHome = this._showHome.bind(this);
        this._onAppChanged = this._onAppChanged.bind(this);

        onWillStart(async () => {
            const enabled = await this._checkEnabled();
            this.state.isEnabled = enabled;
            if (enabled) {
                await this.loadApps();
            }
        });

        onMounted(() => {
            if (!this.state.isEnabled) {
                return;
            }
            document.body.classList.add("o_telesale_menu_enabled");
            this.updateFavicon();
            window.addEventListener(SHOW_HOME_EVENT, this._onShowHome);
            this.env.bus.addEventListener("MENUS:APP-CHANGED", this._onAppChanged);
        });

        onWillUnmount(() => {
            window.removeEventListener(SHOW_HOME_EVENT, this._onShowHome);
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", this._onAppChanged);
            document.body.classList.remove("o_telesale_menu_enabled");
            document.body.classList.remove("o_telesale_home_visible");
        });
    }

    async _checkEnabled() {
        try {
            const result = await rpc("/web/dataset/call_kw/ir.module.module/search_count", {
                model: "ir.module.module",
                method: "search_count",
                args: [[["name", "=", "theme_default"], ["state", "=", "installed"]]],
                kwargs: {},
            });
            return result === 0;
        } catch {
            return true;
        }
    }

    async loadApps() {
        const menus = this.menuService.getApps();
        this.state.apps = menus.map((app) => {
            const menuTree = this.menuService.getMenuAsTree(app.id);
            return {
                id: app.id,
                name: app.name,
                xmlid: app.xmlid,
                actionId: app.actionID,
                appId: app.appID,
                webIcon: app.webIcon,
                webIconData: app.webIconData,
                children: menuTree.childrenTree || [],
            };
        });
    }

    _onAppChanged() {
        if (this.menuService.getCurrentApp()) {
            this.state.isVisible = false;
            document.body.classList.remove("o_telesale_home_visible");
        }
    }

    _showHome() {
        this.state.isVisible = true;
        this.state.searchQuery = "";
        document.body.classList.add("o_telesale_home_visible");
    }

    get filteredApps() {
        const query = (this.state.searchQuery || "").toLowerCase().trim();
        if (!query) {
            return this.state.apps;
        }
        return this.state.apps.filter(app =>
            app.name.toLowerCase().includes(query)
        );
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    getAppIcon(app) {
        if (app.webIconData) {
            if (app.webIconData.startsWith("data:")) {
                return app.webIconData;
            }
            return "data:image/png;base64," + app.webIconData;
        }
        if (app.webIcon) {
            if (typeof app.webIcon === "string") {
                if (app.webIcon.includes(",")) {
                    return null;
                }
                if (app.webIcon.startsWith("/")) {
                    return app.webIcon;
                }
            }
            return "/web/image/ir.ui.menu/" + app.id + "/web_icon";
        }
        return null;
    }

    getAppIconClass(app) {
        if (app.webIcon && typeof app.webIcon === "string") {
            const iconParts = app.webIcon.split(",");
            if (iconParts.length >= 1 && iconParts[0].startsWith("fa")) {
                return iconParts[0];
            }
        }
        const iconMap = {
            "discuss": "fa fa-comments",
            "to-do": "fa fa-edit",
            "calendar": "fa fa-calendar",
            "contacts": "fa fa-address-book",
            "crm": "fa fa-handshake-o",
            "sales": "fa fa-line-chart",
            "project": "fa fa-tasks",
            "email marketing": "fa fa-envelope",
            "surveys": "fa fa-question-circle",
            "employees": "fa fa-users",
            "link tracker": "fa fa-link",
            "apps": "fa fa-th",
            "settings": "fa fa-cog",
            "inventory": "fa fa-cubes",
            "purchase": "fa fa-shopping-cart",
            "invoicing": "fa fa-file-text",
            "website": "fa fa-globe",
            "point of sale": "fa fa-shopping-bag",
            "pos": "fa fa-shopping-bag",
            "dashboards": "fa fa-dashboard",
        };
        const appNameLower = app.name.toLowerCase();
        return iconMap[appNameLower] || "fa fa-cube";
    }

    getAppDataAttr(app) {
        const name = app.name.toLowerCase().replace(/\s+/g, "_");
        return name;
    }

    async onAppClick(app, ev) {
        this.state.searchQuery = "";
        this.state.isVisible = false;
        document.body.classList.remove("o_telesale_home_visible");
        this.menuService.selectMenu(app.id);
    }

    updateFavicon() {
        const timestamp = Date.now();
        const faviconUrl = "/telesale_menu/favicon?t=" + timestamp;

        const existingLinks = document.querySelectorAll("link[rel*='icon']");
        existingLinks.forEach(link => link.remove());

        const link = document.createElement("link");
        link.rel = "icon";
        link.type = "image/x-icon";
        link.href = faviconUrl;
        document.head.appendChild(link);
    }
}

// ============================================================
// NavbarBreadcrumb - Back button to home grid
// ============================================================
export class NavbarBreadcrumb extends Component {
    static template = "telesale_menu.NavbarBreadcrumb";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.state = useState({
            isEnabled: true,
            _tick: 0,
        });

        this._onAppChanged = () => {
            this.state._tick++;
        };

        onWillStart(async () => {
            this.state.isEnabled = document.body.classList.contains("o_telesale_menu_enabled")
                || await this._checkEnabled();
        });

        onMounted(() => {
            if (!this.state.isEnabled) {
                return;
            }
            this.env.bus.addEventListener("MENUS:APP-CHANGED", this._onAppChanged);
        });

        onWillUnmount(() => {
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", this._onAppChanged);
        });
    }

    async _checkEnabled() {
        try {
            const result = await rpc("/web/dataset/call_kw/ir.module.module/search_count", {
                model: "ir.module.module",
                method: "search_count",
                args: [[["name", "=", "theme_default"], ["state", "=", "installed"]]],
                kwargs: {},
            });
            return result === 0;
        } catch {
            return true;
        }
    }

    get hasCurrentApp() {
        return !!this.menuService.getCurrentApp();
    }

    async onHomeClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        window.dispatchEvent(new CustomEvent(SHOW_HOME_EVENT));
    }
}

// ============================================================
// SystrayDateTime - Current date/time display
// ============================================================
export class SystrayDateTime extends Component {
    static template = "telesale_menu.SystrayDateTime";
    static props = ["*"];

    setup() {
        this.state = useState({
            dateTime: "",
        });

        onMounted(() => {
            this._updateDateTime();
            this._interval = setInterval(() => this._updateDateTime(), 1000);
        });

        onWillUnmount(() => {
            if (this._interval) clearInterval(this._interval);
        });
    }

    _updateDateTime() {
        const now = new Date();
        const days = ["Chủ nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"];
        const dayName = days[now.getDay()];
        const dd = String(now.getDate()).padStart(2, '0');
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const yyyy = now.getFullYear();
        const hh = String(now.getHours()).padStart(2, '0');
        const mi = String(now.getMinutes()).padStart(2, '0');
        const ss = String(now.getSeconds()).padStart(2, '0');
        this.state.dateTime = `${dayName}, ${dd}/${mm}/${yyyy} ${hh}:${mi}:${ss}`;
    }
}

// ============================================================
// SystrayActiveTime - Session active time
// ============================================================
export class SystrayActiveTime extends Component {
    static template = "telesale_menu.SystrayActiveTime";
    static props = ["*"];

    setup() {
        this._startTime = Date.now();
        this.state = useState({
            activeTime: "00:00:00",
        });

        this._onStatusChanged = () => {
            this._startTime = Date.now();
            this.state.activeTime = "00:00:00";
        };

        this._onStatusLoaded = (ev) => {
            const { status_change_time } = ev.detail || {};
            if (status_change_time) {
                this._startTime = new Date(status_change_time).getTime();
                this._updateActiveTime();
            }
        };

        onMounted(() => {
            this._updateActiveTime();
            this._interval = setInterval(() => this._updateActiveTime(), 1000);
            window.addEventListener("telesale_status_changed", this._onStatusChanged);
            window.addEventListener("telesale_status_loaded", this._onStatusLoaded);
        });

        onWillUnmount(() => {
            if (this._interval) clearInterval(this._interval);
            window.removeEventListener("telesale_status_changed", this._onStatusChanged);
            window.removeEventListener("telesale_status_loaded", this._onStatusLoaded);
        });
    }

    _updateActiveTime() {
        const elapsed = Math.floor((Date.now() - this._startTime) / 1000);
        const hh = String(Math.floor(elapsed / 3600)).padStart(2, '0');
        const mi = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
        const ss = String(elapsed % 60).padStart(2, '0');
        this.state.activeTime = `${hh}:${mi}:${ss}`;
    }
}


// ============================================================
// Register components
// ============================================================
registry.category("main_components").add("TelesaleMenu", {
    Component: TelesaleMenu,
    props: {},
});

registry.category("main_components").add("NavbarBreadcrumb", {
    Component: NavbarBreadcrumb,
    props: {},
});

registry.category("systray").add("telesale_menu.SystrayDateTime", {
    Component: SystrayDateTime,
}, { sequence: 200 });

registry.category("systray").add("telesale_menu.SystrayActiveTime", {
    Component: SystrayActiveTime,
}, { sequence: 190 });


// ============================================================
// Patch WebClient: show grid home menu after login instead of
// auto-loading the first app
// ============================================================
patch(WebClient.prototype, {
    _loadDefaultApp() {
        if (document.body.classList.contains("o_telesale_menu_enabled")) {
            window.dispatchEvent(new CustomEvent(SHOW_HOME_EVENT));
            return;
        }
        return super._loadDefaultApp();
    },
});
