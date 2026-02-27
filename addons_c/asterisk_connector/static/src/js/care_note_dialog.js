/** @odoo-module **/

import {Component, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class CareNoteDialog extends Component {
    static template = "asterisk_connector.CareNoteDialog";
    static props = {
        endedCall: {type: Object},
    };

    setup() {
        this.phoneService = useService("asterisk_phone");
        this.statePhone = useState(this.phoneService.state);
        this.state = useState({
            note: "",
            selectedTagIds: [],
            isSaving: false,
        });
    }

    get tags() {
        return this.statePhone.crmTags || [];
    }

    get callerDisplay() {
        const call = this.props.endedCall;
        if (!call) return "";
        return call.partner?.name || call.phoneNumber || "Không xác định";
    }

    get directionLabel() {
        const call = this.props.endedCall;
        if (!call) return "";
        return call.direction === "incoming" ? "Cuộc gọi đến" : "Cuộc gọi đi";
    }

    isTagSelected(tagId) {
        return this.state.selectedTagIds.includes(tagId);
    }

    toggleTag(tagId) {
        const idx = this.state.selectedTagIds.indexOf(tagId);
        if (idx >= 0) {
            this.state.selectedTagIds.splice(idx, 1);
        } else {
            this.state.selectedTagIds.push(tagId);
        }
    }

    onNoteInput(ev) {
        this.state.note = ev.target.value;
    }

    async onSave() {
        if (this.state.isSaving) return;
        this.state.isSaving = true;

        try {
            const call = this.props.endedCall;
            if (!call) return;

            await this.phoneService.saveCareNote(
                call.callLogId,
                this.state.note,
                this.state.selectedTagIds,
            );
        } finally {
            this.state.isSaving = false;
        }
    }

    onSkip() {
        this.phoneService.dismissCareNote();
    }
}
