/** @odoo-module **/

import {Component, useState, onMounted, onWillUnmount} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";
import {PhoneWidget} from "./phone_widget";
import {user} from "@web/core/user";

export class SystrayPhone extends Component {
    static template = "asterisk_connector.SystrayPhone";
    static components = {PhoneWidget};
    static props = {};

    setup() {
        this.phoneService = useService("asterisk_phone");
        this.statePhone = useState(this.phoneService.state)
        this.busService = useService("bus_service");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.user = user;

        // Use local state for UI that needs re-rendering
        this.state = useState({
            isOpen: false,
            showStatusDropdown: false,
            currentStatus: 'offline',
        });

        this.statusOptions = [
            {value: 'ready', label: 'Sẵn sàng', color: '#28a745'},
            {value: 'personal_work', label: 'Làm việc riêng', color: '#ffc107'},
            {value: 'zalo_chat', label: 'Chat Zalo', color: '#0068ff'},
            {value: 'create_order', label: 'Tạo đơn', color: '#17a2b8'},
            {value: 'check_order', label: 'Check đơn', color: '#fd7e14'},
            {value: 'training', label: 'Học Đào tạo', color: '#6f42c1'},
            {value: 'team_meeting', label: 'Họp nhóm', color: '#dc3545'},
            {value: 'offline', label: 'Offline', color: '#6c757d'},
        ];

        // Bind methods to ensure correct this context
        this.toggleStatusDropdown = this.toggleStatusDropdown.bind(this);
        this.closeStatusDropdown = this.closeStatusDropdown.bind(this);
        this.changeStatus = this.changeStatus.bind(this);

        // Close dropdown when clicking outside
        this._onDocumentClick = () => {
            if (this.state.showStatusDropdown) {
                this.state.showStatusDropdown = false;
            }
        };

        onWillUnmount(() => {
            document.removeEventListener('click', this._onDocumentClick);
        });

        // Subscribe to bus for incoming calls
        onMounted(async () => {
            // Đảm bảo user đã loaded
            await this.user.context;
            const userId = this.user.userId;
            const channel = `asterisk_call_${userId}`;

            console.log("[SystrayPhone] Setting up bus for channel:", channel, "userId:", userId);

            if (!userId) {
                console.error("[SystrayPhone] userId is undefined! Bus won't work.");
                return;
            }

            // Close dropdown on outside click
            document.addEventListener('click', this._onDocumentClick);

            // Load current status from backend
            await this.loadCurrentStatus();

            // Add the channel to receive notifications (must be before subscribe)
            this.busService.addChannel(channel);
            console.log("[SystrayPhone] Channel added:", channel);

            // Subscribe to specific notification types
            this.busService.subscribe('asterisk/incoming_call', (payload) => {
                console.log("[SystrayPhone] incoming_call received:", payload);
                this._handleIncomingCall(payload);
            });

            this.busService.subscribe('asterisk/outgoing_call', (payload) => {
                console.log("[SystrayPhone] outgoing_call received:", payload);
                this._handleOutgoingCall(payload);
            });

            this.busService.subscribe('asterisk/call_ended', (payload) => {
                console.log("[SystrayPhone] call_ended received:", payload);
                if (!this.phoneService.state.activeCall && !this.phoneService.state.incomingCall) {
                    this.state.isOpen = false;
                }
            });

            console.log("[SystrayPhone] Bus subscriptions setup complete for channel:", channel);
        });
    }

    _handleIncomingCall(payload) {
        // Open widget immediately when incoming call
        this.state.isOpen = true;
        // Also sync with service state
        this.phoneService.state.isWidgetOpen = true;
    }

    _handleOutgoingCall(payload) {
        // Open widget when outgoing call starts
        this.state.isOpen = true;
        this.phoneService.state.isWidgetOpen = true;
    }

    get hasActiveCall() {
        return !!this.phoneService.state.activeCall;
    }

    get hasIncomingCall() {
        return !!this.phoneService.state.incomingCall;
    }

    get isWidgetOpen() {
        return this.state.isWidgetOpen;
    }

    get serviceState() {
        return this.phoneService.state;
    }

    get currentStatusOption() {
        return this.statusOptions.find(s => s.value === this.state.currentStatus) || this.statusOptions[this.statusOptions.length - 1];
    }

    getStatusColor(status) {
        const option = this.statusOptions.find(s => s.value === status);
        return option ? option.color : '#6c757d';
    }

    toggleStatusDropdown = () => {
        this.state.showStatusDropdown = !this.state.showStatusDropdown;
    }

    closeStatusDropdown = () => {
        this.state.showStatusDropdown = false;
    }

    changeStatus = async (newStatus) => {
        if (newStatus === this.state.currentStatus) {
            this.closeStatusDropdown();
            return;
        }

        try {
            const result = await this.orm.call('asterisk.user', 'update_status_for_current_user', [newStatus]);

            if (result.success) {
                this.state.currentStatus = newStatus;
                // Cập nhật status trong phone_service để makeCall có thể kiểm tra
                this.phoneService.updateUserStatus(newStatus);
                // Dispatch event to reset active time in telesale_menu
                window.dispatchEvent(new CustomEvent("telesale_status_changed", {
                    detail: {
                        status: newStatus,
                        status_change_time: result.status_change_time,
                    },
                }));
                this.notification.add(`Trạng thái đã đổi thành: ${this.getStatusLabel(newStatus)}`, {
                    type: 'success',
                });
            } else {
                this.notification.add(result.error || 'Không thể đổi trạng thái', {
                    type: 'danger',
                });
            }
        } catch (error) {
            console.error('Error changing status:', error);
            this.notification.add('Lỗi khi đổi trạng thái', {type: 'danger'});
        }

        this.closeStatusDropdown();
    }

    getStatusLabel(status) {
        const option = this.statusOptions.find(s => s.value === status);
        return option ? option.label : status;
    }

    async loadCurrentStatus() {
        // Load trạng thái hiện tại của agent từ backend
        try {
            const result = await this.orm.call('asterisk.user', 'get_current_user_status', []);
            if (result.success && result.status) {
                this.state.currentStatus = result.status;
                // Cập nhật status trong phone_service để đồng bộ
                this.phoneService.updateUserStatus(result.status);
                // Dispatch event with status_change_time so SystrayActiveTime can restore timer on F5
                window.dispatchEvent(new CustomEvent("telesale_status_loaded", {
                    detail: {
                        status: result.status,
                        status_change_time: result.status_change_time,
                    },
                }));
                console.log('[SystrayPhone] Loaded current status:', result.status, 'change_time:', result.status_change_time);
            }
        } catch (error) {
            console.error('[SystrayPhone] Error loading current status:', error);
        }
    }

    toggleWidget() {
        this.state.isOpen = !this.state.isOpen;
        // Sync with service state
        this.phoneService.state.isWidgetOpen = this.state.isOpen;
        if (this.state.isOpen && this.phoneService.state.callHistory.length === 0) {
            this.phoneService.loadCallHistory();
        }
    }
}

export const systrayItem = {
    Component: SystrayPhone,
};

registry.category("systray").add("asterisk_connector.SystrayPhone", systrayItem, {sequence: 99});
