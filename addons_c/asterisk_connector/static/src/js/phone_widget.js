/** @odoo-module **/

import {Component, useState, useRef, onMounted, onWillUnmount} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";

export class PhoneWidget extends Component {
    static template = "asterisk_connector.PhoneWidget";
    static components = {};
    static props = {};

    setup() {
        this.phoneService = useService("asterisk_phone");
        this.statePhone = useState(this.phoneService.state)
        this.state = useState({
            activeTab: "dialpad",
            phoneNumber: "",
            callTimer: 0,
            transferSearch: "",
            selectedCallType: "softphone",
            showDialpad: true,
            isMuted: false,
            isOnHold: false,
            showTransferPanel: false,
            showInCallDialpad: false,
            careResult: "",
            careNote: "",
            // Settings tab state
            availableExtensions: [],
            selectedExtension: null,
            preferredCallType: "softphone",
            settingsLoaded: false,
            dialpadKeys: [
                {'main': '1'},
                {
                    'main': '2',
                    'sub': 'ABC'
                },
                {
                    'main': '3',
                    'sub': 'DEF',
                },
                {
                    'main': '4',
                    'sub': 'GHI',
                },
                {
                    'main': '5',
                    'sub': 'JKL',
                },
                {
                    'main': '6',
                    'sub': 'MNO',
                },
                {
                    'main': '7',
                    'sub': 'PQRS',
                },
                {
                    'main': '8',
                    'sub': 'TUV',
                },
                {
                    'main': '9',
                    'sub': 'WXYZ',
                },
                {'main': '*'},
                {
                    'main': '0',
                    'sub': '+',
                },
                {'main': '#'},
            ]
        });

        this.phoneInputRef = useRef("phoneInput");
        this.timerInterval = null;
        // Track previous call data for detecting auto-ended calls
        this._lastActiveCallData = null;

        onMounted(() => {
            // Start timer if there's already an active call
            if (this.serviceState.activeCall) {
                this.startCallTimer();
            }
            // Check for active call changes periodically
            this._checkCallStateInterval = setInterval(async () => {
                const activeCall = this.serviceState.activeCall;
                if (activeCall) {
                    // Call is active — keep tracking its data
                    if (!this._lastActiveCallData) {
                        this.startCallTimer();
                    }
                    this._lastActiveCallData = {
                        callLogId: activeCall.callLogId,
                        direction: activeCall.direction,
                        phoneNumber: activeCall.phoneNumber,
                        partner: activeCall.partner || null,
                        answerTime: activeCall.answerTime || null,
                        startTime: activeCall.startTime || null,
                    };
                } else if (this._lastActiveCallData) {
                    // Call just ended automatically (other party hung up / AMI event)
                    const lastCall = this._lastActiveCallData;
                    this._lastActiveCallData = null;
                    this.stopCallTimer();

                    // Auto-save care note with data collected during the call
                    if (lastCall.callLogId) {
                        await this.phoneService.saveCareNote(
                            lastCall.callLogId,
                            this.state.careNote,
                            [],
                            this.state.careResult,
                            lastCall.direction,
                        );
                    }

                    this.state.isMuted = false;
                    this.state.isOnHold = false;
                    this.state.showTransferPanel = false;
                    this.state.showInCallDialpad = false;
                    this.state.careResult = "";
                    this.state.careNote = "";
                    this.state.activeTab = "dialpad";
                }
            }, 500);
        });

        onWillUnmount(() => {
            this.stopCallTimer();
            if (this._checkCallStateInterval) {
                clearInterval(this._checkCallStateInterval);
            }
        });
    }

    get serviceState() {
        return this.phoneService.state;
    }

    get incomingCallerDisplay() {
        const incoming = this.serviceState.incomingCall;
        if (!incoming) return "";
        return incoming.partner?.name || incoming.callerId || incoming.phoneNumber || "Không xác định";
    }

    get activeCallerName() {
        const active = this.serviceState.activeCall;
        if (!active) return "";
        return active.partner?.name || active.callerId || active.phoneNumber || "Cuộc gọi";
    }

    get callResultOptions() {
        return [
            {value: 'connected', label: 'Kết nối thành công'},
            {value: 'no_answer', label: 'Không trả lời'},
            {value: 'busy', label: 'Máy bận'},
            {value: 'rejected', label: 'Từ chối cuộc gọi'},
            {value: 'unreachable', label: 'Không liên lạc được'},
            {value: 'wrong_number', label: 'Sai số'},
        ];
    }

    onCallResultChange(ev) {
        this.state.careResult = ev.target.value;
    }

    onCareNoteInput(ev) {
        this.state.careNote = ev.target.value;
    }

    get filteredExtensions() {
        const search = this.state.transferSearch.toLowerCase();
        if (!search) return this.serviceState.extensions;

        return this.serviceState.extensions.filter(ext =>
            ext.extension.includes(search) ||
            ext.user_name.toLowerCase().includes(search)
        );
    }

    // Tab management
    onTabDialpad() {
        this.setActiveTab("dialpad");
    }

    onTabHistory() {
        this.setActiveTab("history");
    }

    onTabTransfer() {
        this.setActiveTab("transfer");
    }

    onTabSettings() {
        this.setActiveTab("settings");
        // Load user extensions when opening settings tab
        if (!this.state.settingsLoaded) {
            this.loadUserExtensions();
        }
    }

    async loadUserExtensions() {
        const extensions = await this.phoneService.loadUserExtensions();
        this.state.availableExtensions = extensions;

        const config = this.serviceState.userConfig;

        if (config && config.extension) {
            // Đã có config - chọn extension đang dùng
            this.state.selectedExtension = config.extension;
        } else if (extensions.length > 0) {
            // Chưa có config - chọn extension đầu tiên mặc định
            this.state.selectedExtension = extensions[0].extension;
        }

        // Set preferred call type
        if (config && config.preferred_call_type) {
            this.state.preferredCallType = config.preferred_call_type;
        } else if (config && config.call_type) {
            this.state.preferredCallType = config.call_type === 'ipphone' ? 'ipphone' : 'softphone';
        } else {
            this.state.preferredCallType = 'softphone';
        }

        this.state.settingsLoaded = true;
    }

    onExtensionSelect(extension) {
        this.state.selectedExtension = extension;
    }

    onExtensionSelectFromDropdown(ev) {
        this.state.selectedExtension = ev.target.value;
    }

    onPreferredCallTypeChange = (callType) => {
        this.state.preferredCallType = callType;
    }

    async saveSettings() {
        const success = await this.phoneService.saveUserSettings({
            extension: this.state.selectedExtension,
            preferred_call_type: this.state.preferredCallType,
        });
        if (success) {
            this.phoneService.notification.add("Đã lưu cấu hình", {type: "success"});
            // Reload config to apply changes
            await this.phoneService.reloadUserConfig();
        } else {
            this.phoneService.notification.add("Không thể lưu cấu hình", {type: "danger"});
        }
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;

        if (tab === "history") {
            this.phoneService.loadCallHistory();
        } else if (tab === "transfer") {
            console.log("Loading extensions for transfer tab...");
            this.phoneService.loadExtensions().then(() => {
                console.log("Extensions loaded:", this.serviceState.extensions);
            });
        } else if (tab === "settings") {
            this.loadUserExtensions();
        }
    }

    // Dialpad - bound methods for each key
    onKey1() {
        this._pressKey('1');
    }

    onKey2() {
        this._pressKey('2');
    }

    onKey3() {
        this._pressKey('3');
    }

    onKey4() {
        this._pressKey('4');
    }

    onKey5() {
        this._pressKey('5');
    }

    onKey6() {
        this._pressKey('6');
    }

    onKey7() {
        this._pressKey('7');
    }

    onKey8() {
        this._pressKey('8');
    }

    onKey9() {
        this._pressKey('9');
    }

    onKey0() {
        this._pressKey('0');
    }

    onKeyStar() {
        this._pressKey('*');
    }

    onKeyHash() {
        this._pressKey('#');
    }

    _pressKey(key) {
        this.state.phoneNumber += key;
        this.playKeyTone(key);
    }

    onBackspace() {
        this.state.phoneNumber = this.state.phoneNumber.slice(0, -1);
    }

    clearPhoneNumber() {
        this.state.phoneNumber = "";
    }

    toggleDialpad() {
        this.state.showDialpad = !this.state.showDialpad;
    }

    onPhoneInputChange(ev) {
        // Allow only digits and some special characters
        this.state.phoneNumber = ev.target.value.replace(/[^\d+*#]/g, "");
    }

    playKeyTone(key) {
        // DTMF tone frequencies
        const tones = {
            "1": [697, 1209], "2": [697, 1336], "3": [697, 1477],
            "4": [770, 1209], "5": [770, 1336], "6": [770, 1477],
            "7": [852, 1209], "8": [852, 1336], "9": [852, 1477],
            "*": [941, 1209], "0": [941, 1336], "#": [941, 1477],
        };

        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const frequencies = tones[key];

            if (frequencies) {
                frequencies.forEach(freq => {
                    const oscillator = audioContext.createOscillator();
                    const gainNode = audioContext.createGain();

                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);

                    oscillator.frequency.value = freq;
                    oscillator.type = "sine";
                    gainNode.gain.value = 0.1;

                    oscillator.start();
                    oscillator.stop(audioContext.currentTime + 0.1);
                });
            }
        } catch (err) {
            // Ignore audio errors
        }
    }

    // Call actions
    async makeCall() {
        if (!this.state.phoneNumber) return;

        // Xác định loại gọi dựa trên call_type từ user config
        const config = this.serviceState.userConfig;
        let callType = 'softphone'; // mặc định

        if (config) {
            if (config.call_type === 'ipphone') {
                callType = 'ipphone';
            } else if (config.call_type === 'both') {
                // Khi 'both', dùng lựa chọn từ UI
                callType = this.state.selectedCallType;
            }
            // 'softphone' thì giữ nguyên mặc định
        }

        // Gọi service với call_type đã xác định
        const success = await this.phoneService.makeCall(this.state.phoneNumber, callType);
        if (success) {
            this.state.phoneNumber = "";
        }
    }

    onCallTypeChange(ev) {
        this.state.selectedCallType = ev.target.value;
    }

    hangupCall() {
        this.phoneService.hangupCall();
        this.stopCallTimer();
    }

    // Incoming call actions (inline banner)
    async answerIncomingCall() {
        console.log("Answer incoming call clicked");
        await this.phoneService.answerCall();
        this.phoneService.stopRingtone();
        // Force re-render to show active call UI
        this.render();
    }

    async rejectIncomingCall() {
        const channel = this.serviceState.incomingCall?.channel;
        await this.phoneService.hangupCall(channel);
        this.phoneService.stopRingtone();
        // Reset to dialpad tab and force render
        this.state.activeTab = "dialpad";
        this.render();
    }

    // Dismiss incoming call notification (for IP phone mode)
    dismissIncomingCall() {
        this.phoneService.dismissIncomingCall();
        this.state.activeTab = "dialpad";
        this.render();
    }

    // Check if incoming call is for IP phone (no answer/reject buttons)
    get isIPPhoneIncoming() {
        const callType = this.serviceState.incomingCall?.callType;
        return callType === 'ipphone';
    }

    // Active call controls
    async toggleMute() {
        const newMuteState = !this.state.isMuted;
        const success = await this.phoneService.muteCall(newMuteState);
        if (success) {
            this.state.isMuted = newMuteState;
        }
    }

    async toggleHold() {
        const newHoldState = !this.state.isOnHold;
        const success = await this.phoneService.holdCall(newHoldState);
        if (success) {
            this.state.isOnHold = newHoldState;
        }
    }

    toggleTransferPanel() {
        this.state.showTransferPanel = !this.state.showTransferPanel;
        this.state.showInCallDialpad = false; // Close dialpad when opening transfer
        if (this.state.showTransferPanel) {
            this.phoneService.loadExtensions();
        }
    }

    toggleInCallDialpad() {
        this.state.showInCallDialpad = !this.state.showInCallDialpad;
        this.state.showTransferPanel = false; // Close transfer when opening dialpad
    }

    sendDTMF(digit) {
        this.phoneService.sendDTMF(digit);
    }

    async hangupActiveCall() {
        const activeCall = this.serviceState.activeCall;
        const channel = activeCall?.channel;
        const callLogId = activeCall?.callLogId;
        const direction = activeCall?.direction;

        // Clear tracked data so _checkCallStateInterval doesn't double-trigger
        this._lastActiveCallData = null;

        // Save care note before hanging up
        if (callLogId) {
            await this.phoneService.saveCareNote(
                callLogId,
                this.state.careNote,
                [],
                this.state.careResult,
                direction,
            );
        }

        await this.phoneService.hangupCall(channel);
        this.stopCallTimer();
        this.state.isMuted = false;
        this.state.isOnHold = false;
        this.state.showTransferPanel = false;
        this.state.showInCallDialpad = false;
        this.state.careResult = "";
        this.state.careNote = "";
        // Return to dialpad tab
        this.state.activeTab = "dialpad";
    }

    async transferTo(extension) {
        const success = await this.phoneService.transferCall(extension);
        if (success) {
            this.state.showTransferPanel = false;
            this.state.transferSearch = "";
        }
    }

    // History
    onHistoryItemClick(ev) {
        const phone = ev.currentTarget.dataset.phone;
        if (phone) {
            this.state.phoneNumber = phone;
            this.state.activeTab = "dialpad";
        }
    }

    // Transfer
    async onExtensionClick(ev) {
        const ext = ev.currentTarget.dataset.ext;
        if (ext) {
            const success = await this.phoneService.transferCall(ext);
            if (success) {
                this.state.transferSearch = "";
            }
        }
    }

    // Call timer - only counts when call is answered (has answerTime)
    startCallTimer() {
        this.stopCallTimer(); // Clear any existing timer first
        this.timerInterval = setInterval(() => {
            if (this.serviceState.activeCall?.answerTime) {
                // Only count when call is answered
                this.state.callTimer = Math.floor(
                    (new Date() - new Date(this.serviceState.activeCall.answerTime)) / 1000
                );
            } else {
                // During dialing, keep timer at 0
                this.state.callTimer = 0;
            }
        }, 1000);
    }

    stopCallTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.state.callTimer = 0;
    }

    get formattedTimer() {
        return this.phoneService.formatDuration(this.state.callTimer);
    }

    get isDialing() {
        return this.serviceState.activeCall &&
            this.serviceState.activeCall.state === 'dialing' &&
            !this.serviceState.activeCall.answerTime;
    }

    get callStatusText() {
        if (!this.serviceState.activeCall) {
            return;
        }
        if (this.isDialing) {
            this.startCallTimer();
        }
        return this.formattedTimer;
    }

    // Close widget - hang up if there's an active call
    closeWidget() {
        if (this.serviceState.activeCall) {
            // If there's an active call, hang up first
            this.hangupActiveCall();
        } else if (this.serviceState.incomingCall) {
            // If there's an incoming call, reject it
            this.rejectIncomingCall();
        }
        this.phoneService.state.isWidgetOpen = false;
    }

    // Direction icon
    getDirectionClass(item) {
        if (item.state === "no_answer" || item.state === "busy") {
            return "missed";
        }
        return item.direction;
    }

    getDirectionIcon(item) {
        if (item.state === "no_answer" || item.state === "busy") {
            return "fa-phone-slash";
        }
        return item.direction === "incoming" ? "fa-arrow-down" : "fa-arrow-up";
    }

    formatDateTime(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        const now = new Date();
        const diff = now - date;

        // Today
        if (diff < 86400000 && date.getDate() === now.getDate()) {
            return date.toLocaleTimeString("vi-VN", {hour: "2-digit", minute: "2-digit"});
        }

        // This week
        if (diff < 604800000) {
            return date.toLocaleDateString("vi-VN", {weekday: "short", hour: "2-digit", minute: "2-digit"});
        }

        return date.toLocaleDateString("vi-VN", {day: "2-digit", month: "2-digit"});
    }
}

