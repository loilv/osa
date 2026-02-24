/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { LivechatSidebarFormController } from "./livechat_sidebar_form_controller";
import { LivechatSidebarFormRenderer } from "./livechat_sidebar_form_renderer";

export const LivechatSidebarFormView = {
    ...formView,
    Controller: LivechatSidebarFormController,
    Renderer: LivechatSidebarFormRenderer,
    display: { controlPanel: false },
};

registry.category("views").add("livechat_session_form", LivechatSidebarFormView, { force: true });
