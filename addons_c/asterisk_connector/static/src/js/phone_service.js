/** @odoo-module **/

import {registry} from "@web/core/registry";
import {reactive} from "@odoo/owl";
import {rpc} from "@web/core/network/rpc";
import {user} from "@web/core/user";

const { SIP } = window;

export const asteriskPhoneService = {
    dependencies: ["bus_service", "notification"],

    start(env, {bus_service, notification}) {
        const state = reactive({
            isConfigured: false,
            userConfig: null,
            activeCall: null,
            incomingCall: null,
            endedCall: null,
            crmTags: [],
            callHistory: [],
            extensions: [],
            isWidgetOpen: false,
            sipRegistered: false,
        });

        // Ringtone audio
        let ringtoneAudio = null;

        // SIP Client for WebRTC
        let sipClient = null;

        // Load user config on start
        async function loadUserConfig() {
            try {
                const result = await rpc("/asterisk/get_user_config");
                if (result.success && result.data && result.data.id) {
                    state.userConfig = result.data;
                    state.isConfigured = true;

                    console.log("Asterisk user config loaded:", {
                        extension: result.data.extension,
                        ws_enabled: result.data.ws_enabled,
                        has_sip_password: !!result.data.sip_password,
                        ws_url: result.data.ws_url,
                    });

                    // Subscribe to bus channel for incoming calls (AMI mode)
                    const channel = `asterisk_call_${user.userId}`;

                    // Subscribe to specific notification types
                    bus_service.subscribe('asterisk/incoming_call', (payload) => {
                        console.log("asterisk/incoming_call received:", payload);
                        handleIncomingCall(payload);
                    });
                    bus_service.subscribe('asterisk/outgoing_call', (payload) => {
                        console.log("asterisk/outgoing_call received:", payload);
                        handleOutgoingCallFromIPPhone(payload);
                    });
                    bus_service.subscribe('asterisk/call_answered', (payload) => {
                        console.log("asterisk/call_answered received:", payload);
                        handleCallAnswered(payload);
                    });
                    bus_service.subscribe('asterisk/call_ended', (payload) => {
                        console.log("asterisk/call_ended received:", payload);
                        handleCallEnded(payload);
                    });

                    // Add the channel to receive notifications
                    bus_service.addChannel(channel);

                    // Initialize WebRTC if enabled
                    if (result.data.ws_enabled && result.data.sip_password) {
                        console.log("WebRTC is enabled, initializing SIP client...");
                        initSipClient(result.data);
                    } else {
                        console.log("WebRTC not initialized:",
                            !result.data.ws_enabled ? "ws_enabled=false" : "",
                            !result.data.sip_password ? "sip_password not set" : "");
                    }
                }
            } catch (error) {
                console.error("Failed to load Asterisk config:", error);
            }
        }

        // Initialize SIP Client for WebRTC using SIP.js directly
        async function initSipClient(config) {
            try {
                console.log("Initializing SIP.js directly with config:", {
                    wsUrl: config.ws_url,
                    domain: config.sip_domain,
                    extension: config.extension,
                    hasPassword: !!config.sip_password,
                });

                const uri = SIP.UserAgent.makeURI(`sip:${config.extension}@${config.sip_domain}`);
                if (!uri) {
                    throw new Error('Failed to create SIP URI');
                }

                const userAgentOptions = {
                    uri: uri,
                    transportOptions: {
                        wsServers: config.ws_url,
                    },
                    authorizationUsername: config.extension,
                    authorizationPassword: config.sip_password,
                    register: false,
                    sessionDescriptionHandlerFactoryOptions: {
                        constraints: {
                            audio: true,
                            video: false,
                        },
                        iceCheckingTimeout: 500,
                        peerConnectionConfiguration: {
                            iceServers: [
                                { urls: 'stun:stun.l.google.com:19302' },
                                { urls: 'stun:stun1.l.google.com:19302' },
                            ],
                            iceTransportPolicy: 'all',
                            bundlePolicy: 'balanced',
                            rtcpMuxPolicy: 'require',
                        },
                    },
                    delegate: {
                        onInvite: (invitation) => {
                            handleSIPIncomingCall(invitation);
                        },
                    },
                };

                sipClient = {
                    userAgent: new SIP.UserAgent(userAgentOptions),
                    registerer: null,
                    session: null,
                    registered: false,
                };

                sipClient.userAgent.stateChange.addListener((newState) => {
                    console.log('[PhoneService] UserAgent state:', newState);
                    if (newState === SIP.UserAgentState.Stopped) {
                        sipClient.registered = false;
                        state.sipRegistered = false;
                    }
                });

                await sipClient.userAgent.start();

                // Create Registerer
                sipClient.registerer = new SIP.Registerer(sipClient.userAgent);
                
                sipClient.registerer.stateChange.addListener((newState) => {
                    console.log('[PhoneService] Registerer state:', newState);
                    if (newState === SIP.RegistererState.Registered) {
                        sipClient.registered = true;
                        state.sipRegistered = true;
                        console.log('[PhoneService] SIP registered');
                    } else if (newState === SIP.RegistererState.Unregistered) {
                        sipClient.registered = false;
                        state.sipRegistered = false;
                        console.log('[PhoneService] SIP unregistered');
                    }
                });

                await sipClient.registerer.register();

            } catch (error) {
                console.error("Failed to initialize SIP client:", error);
            }
        }

        // Handle SIP incoming call
        async function handleSIPIncomingCall(invitation) {
            console.log("[PhoneService] SIP incoming call from:", invitation.remoteIdentity.uri.user);
            
            // Check user config - if ipphone mode, reject SIP call
            const userCallType = state.userConfig?.call_type || 'softphone';
            console.log("[PhoneService] User call type:", userCallType);
            
            if (userCallType === 'ipphone') {
                console.log("[PhoneService] IP Phone mode - rejecting SIP incoming call");
                invitation.reject();
                return;
            }
            
            console.log("[PhoneService] Invitation state:", invitation.state);
            
            sipClient.session = invitation;

            // Tạo call log cho cuộc gọi đến qua softphone
            const callerNumber = invitation.remoteIdentity.uri.user;
            let callLogId = null;
            try {
                const logResult = await rpc("/asterisk/log_softphone_call", {
                    phone_number: callerNumber,
                    direction: 'incoming',
                    caller_id: callerNumber,
                });
                if (logResult.success) {
                    callLogId = logResult.call_log_id;
                }
            } catch (err) {
                console.error('[PhoneService] Error creating incoming call log:', err);
            }

            invitation.delegate = {
                onBye: (bye) => {
                    console.log("[PhoneService] Received BYE");
                    bye.accept();
                    cleanupSIPCall();
                },
                onAck: (ackRequest) => {
                    console.log("[PhoneService] Received ACK from caller, call fully established");
                },
                onAckTimeout: () => {
                    console.warn("[PhoneService] ACK timeout - caller did not send ACK");
                },
            };

            invitation.stateChange.addListener((newState) => {
                console.log('[PhoneService] Invitation state changed to:', newState);
                if (newState === SIP.SessionState.Established) {
                    console.log('[PhoneService] Session fully established (ACK received)');
                    // Cập nhật call log: answered
                    if (callLogId) {
                        rpc("/asterisk/update_call_log", {call_log_id: callLogId, state: 'answered'}).catch(e => console.error(e));
                    }
                }
                if (newState === SIP.SessionState.Terminated) {
                    // Cập nhật call log: hangup
                    if (callLogId) {
                        rpc("/asterisk/update_call_log", {call_log_id: callLogId, state: 'hangup'}).catch(e => console.error(e));
                    }
                    cleanupSIPCall();
                }
            });

            handleIncomingCall({
                phone_number: callerNumber,
                caller_id: callerNumber,
                call_log_id: callLogId,
                start_time: new Date().toISOString(),
                partner: null,
            });
        }

        // Cleanup SIP call
        function cleanupSIPCall() {
            sipClient.session = null;
            state.activeCall = null;
            state.incomingCall = null;
            stopRingtone();
        }

        // Helper to check if SIP is registered
        function isSIPRegistered() {
            return sipClient && sipClient.registered;
        }

        // Helper to check if SIP has active call
        function hasSIPActiveCall() {
            return sipClient && sipClient.session && 
                   (sipClient.session.state === SIP.SessionState.Established || 
                    sipClient.session.state === SIP.SessionState.Establishing ||
                    sipClient.session.state === SIP.SessionState.Initial);
        }

        // Make SIP call
        async function makeSIPCall(targetNumber, callLogId) {
            if (!sipClient || !sipClient.registered) {
                console.error('[PhoneService] SIP not registered');
                return false;
            }

            try {
                const targetUri = SIP.UserAgent.makeURI(`sip:${targetNumber}@${state.userConfig.sip_domain}`);
                if (!targetUri) {
                    throw new Error('Invalid target URI');
                }

                const inviter = new SIP.Inviter(sipClient.userAgent, targetUri, {
                    sessionDescriptionHandlerOptions: {
                        constraints: { audio: true, video: false },
                    },
                });

                inviter.stateChange.addListener((newState) => {
                    console.log('[PhoneService] Inviter state:', newState);
                    switch (newState) {
                        case SIP.SessionState.Established:
                            console.log('[PhoneService] Call established');
                            setupRemoteAudio(inviter);
                            state.activeCall = {
                                phoneNumber: targetNumber,
                                direction: "outgoing",
                                state: "answered",
                                startTime: new Date(),
                                answerTime: new Date(),
                                callLogId: callLogId,
                                callType: 'softphone',
                            };
                            // Cập nhật call log: answered
                            if (callLogId) {
                                rpc("/asterisk/update_call_log", {call_log_id: callLogId, state: 'answered'}).catch(e => console.error(e));
                            }
                            break;
                        case SIP.SessionState.Terminated:
                            // Cập nhật call log: hangup
                            if (callLogId) {
                                rpc("/asterisk/update_call_log", {call_log_id: callLogId, state: 'hangup'}).catch(e => console.error(e));
                            }
                            cleanupSIPCall();
                            break;
                    }
                });

                await inviter.invite();
                sipClient.session = inviter;
                return true;
            } catch (error) {
                console.error('[PhoneService] SIP call error:', error);
                return false;
            }
        }

        // Accept SIP call
        async function acceptSIPCall() {
            if (!sipClient || !sipClient.session) {
                console.error('[PhoneService] No incoming call to accept');
                return false;
            }

            const session = sipClient.session;
            console.log('[PhoneService] Accepting call, current state:', session.state);
            console.log('[PhoneService] Session type:', session instanceof SIP.Invitation ? 'Invitation' : 'Inviter');

            try {
                // Log the session description handler state before accepting
                const sdh = session.sessionDescriptionHandler;
                console.log('[PhoneService] SDH before accept:', sdh ? 'exists' : 'null');
                if (sdh && sdh.peerConnection) {
                    console.log('[PhoneService] PeerConnection state:', sdh.peerConnection.signalingState);
                }

                // Setup delegate before accepting to catch ACK
                session.delegate = {
                    ...session.delegate,
                    onAck: (ackRequest) => {
                        console.log("[PhoneService] Received ACK after accept, call confirmed");
                        console.log("[PhoneService] ACK request:", ackRequest);
                    },
                    onAckTimeout: () => {
                        console.warn("[PhoneService] ACK timeout after sending 200 OK");
                    },
                };

                // Accept returns a promise that resolves when 200 OK is sent
                console.log('[PhoneService] Calling session.accept()...');
                await session.accept({
                    sessionDescriptionHandlerOptions: {
                        constraints: { audio: true, video: false },
                    },
                });

                console.log('[PhoneService] session.accept() completed - 200 OK should be sent');
                console.log('[PhoneService] Session state after accept:', session.state);

                setupRemoteAudio(session);
                
                state.activeCall = {
                    ...state.incomingCall,
                    direction: "incoming",
                    state: "answered",
                    answerTime: new Date(),
                };
                state.incomingCall = null;
                stopRingtone();
                return true;
            } catch (error) {
                console.error('[PhoneService] Accept call error:', error);
                console.error('[PhoneService] Error stack:', error.stack);
                return false;
            }
        }

        // Hangup SIP call
        function hangupSIPCall() {
            if (!sipClient || !sipClient.session) return;

            try {
                const session = sipClient.session;
                switch (session.state) {
                    case SIP.SessionState.Establishing:
                        if (session instanceof SIP.Inviter) {
                            session.cancel();
                        }
                        break;
                    case SIP.SessionState.Established:
                        session.bye();
                        break;
                    case SIP.SessionState.Initial:
                        if (session instanceof SIP.Invitation) {
                            session.reject();
                        }
                        break;
                }
            } catch (error) {
                console.error('[PhoneService] Hangup error:', error);
            }
            cleanupSIPCall();
        }

        // Reject SIP call
        function rejectSIPCall() {
            if (sipClient && sipClient.session instanceof SIP.Invitation) {
                try {
                    sipClient.session.reject();
                } catch (error) {
                    console.error('[PhoneService] Reject error:', error);
                }
            }
            cleanupSIPCall();
        }

        // Set SIP mute
        function setSIPMute(mute) {
            if (!sipClient || !sipClient.session) return false;

            const sdh = sipClient.session.sessionDescriptionHandler;
            if (!sdh || !sdh.peerConnection) return false;

            const senders = sdh.peerConnection.getSenders();
            const audioSender = senders.find(sender => sender.track && sender.track.kind === 'audio');
            
            if (audioSender && audioSender.track) {
                audioSender.track.enabled = !mute;
                return true;
            }
            return false;
        }

        // Send SIP DTMF
        function sendSIPDTMF(digit) {
            if (!sipClient || !sipClient.session) return false;
            try {
                sipClient.session.dtmf(digit);
                return true;
            } catch (error) {
                console.error('[PhoneService] DTMF error:', error);
                return false;
            }
        }

        // Setup remote audio for SIP session
        function setupRemoteAudio(session) {
            console.log('[PhoneService] Setting up remote audio...');
            const sdh = session.sessionDescriptionHandler;
            if (!sdh) {
                console.warn('[PhoneService] No session description handler');
                return;
            }

            // Method 1: Use ontrack event for new tracks
            if (sdh.peerConnection) {
                console.log('[PhoneService] Setting up peer connection ontrack');
                
                // Check if there are already remote streams
                const receivers = sdh.peerConnection.getReceivers();
                console.log('[PhoneService] Number of receivers:', receivers.length);
                
                receivers.forEach((receiver, idx) => {
                    if (receiver.track) {
                        console.log(`[PhoneService] Receiver ${idx} track:`, receiver.track.kind, receiver.track.readyState);
                    }
                });

                sdh.peerConnection.ontrack = (event) => {
                    console.log('[PhoneService] Received remote track:', event.track.kind);
                    const remoteAudio = new Audio();
                    remoteAudio.autoplay = true;
                    remoteAudio.srcObject = event.streams[0];
                    console.log('[PhoneService] Remote audio stream attached');
                };
            }

            // Method 2: Check for existing remote media stream
            if (sdh.remoteMediaStream) {
                console.log('[PhoneService] Using existing remote media stream');
                const remoteAudio = new Audio();
                remoteAudio.autoplay = true;
                remoteAudio.srcObject = sdh.remoteMediaStream;
            }

            // Log connection state
            if (sdh.peerConnection) {
                sdh.peerConnection.onconnectionstatechange = () => {
                    console.log('[PhoneService] Peer connection state:', sdh.peerConnection.connectionState);
                };
                sdh.peerConnection.oniceconnectionstatechange = () => {
                    console.log('[PhoneService] ICE connection state:', sdh.peerConnection.iceConnectionState);
                };
            }
        }

        // Handle bus notifications
        function handleBusNotification(message, payload) {
            // payload contains the actual notification type and data
            const notifType = payload?.type || message?.type;
            const data = payload || message;

            console.log("Bus notification received - type:", notifType, "data:", data);

            if (notifType === "incoming_call" || notifType === "asterisk/incoming_call") {
                handleIncomingCall(data);
            } else if (notifType === "outgoing_call" || notifType === "asterisk/outgoing_call") {
                handleOutgoingCallFromIPPhone(data);
            } else if (notifType === "call_answered" || notifType === "asterisk/call_answered") {
                handleCallAnswered(data);
            } else if (notifType === "call_ended" || notifType === "asterisk/call_ended") {
                handleCallEnded(data);
            }
        }

        function handleOutgoingCallFromIPPhone(data) {
            console.log("Outgoing call from IP phone:", data);

            state.activeCall = {
                callLogId: data.call_log_id,
                phoneNumber: data.phone_number,
                channel: data.channel,
                uniqueId: data.unique_id,
                partner: data.partner || null,
                direction: "outgoing",
                state: "dialing",
                startTime: data.start_time ? new Date(data.start_time) : new Date(),
                fromIPPhone: true,
            };


            notification.add(`Đang gọi tới ${data.phone_number} (IP Phone)`, {type: "info"});
        }

        function handleCallAnswered(data) {
            console.log("[PhoneService] handleCallAnswered:", data, "current activeCall:", state.activeCall);
            if (state.activeCall && state.activeCall.uniqueId === data.unique_id) {
                state.activeCall.state = "answered";
                state.activeCall.answerTime = new Date();
                console.log("[PhoneService] Call answered, answerTime set:", state.activeCall.answerTime);


            } else {
                console.warn("[PhoneService] Call answered but uniqueId mismatch or no activeCall:",
                    {activeCallUniqueId: state.activeCall?.uniqueId, dataUniqueId: data.unique_id});
            }
        }

        function handleCallEnded(data) {
            if (state.activeCall && state.activeCall.uniqueId === data.unique_id) {
                state.activeCall = null;
                state.incomingCall = null;
                stopRingtone();
            }
        }

        // Handle incoming call
        function handleIncomingCall(data) {
            console.log("Handling incoming call:", data);

            // Check call type - ipphone mode only shows info, no answer/reject
            const callType = data.call_type || 'softphone';
            
            // Check user config - if softphone mode, ignore AMI incoming call
            const userCallType = state.userConfig?.call_type || 'softphone';
            console.log("[PhoneService] User call type:", userCallType, "Call type from data:", callType);
            
            // If this is from AMI (has channel) and user is in softphone mode, skip
            if (data.channel && userCallType === 'softphone') {
                console.log("[PhoneService] Softphone mode - ignoring AMI incoming call");
                return;
            }

            state.incomingCall = {
                callLogId: data.call_log_id,
                phoneNumber: data.phone_number,
                callerId: data.caller_id,
                channel: data.channel,
                uniqueId: data.unique_id,
                partner: data.partner || null,
                startTime: data.start_time ? new Date(data.start_time) : new Date(),
                callType: callType,  // 'softphone', 'ipphone', or 'both'
            };

            console.log("Incoming call state set:", state.incomingCall);

            // Auto-open widget when incoming call
            state.isWidgetOpen = true;


            // Only play ringtone for softphone or both mode
            if (callType === 'softphone' || callType === 'both') {
                playRingtone();
            }

            // Show browser notification if permitted
            showBrowserNotification(data);
        }

        // Play ringtone using Web Audio API
        function playRingtone() {
            stopRingtone();

            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();

                // Create ringtone pattern
                function playRingTone() {
                    if (!state.incomingCall) return;

                    // Ring tone frequencies (standard phone ring)
                    const frequencies = [440, 480];
                    const oscillators = [];
                    const gainNode = audioContext.createGain();
                    gainNode.connect(audioContext.destination);
                    gainNode.gain.value = 0.3;

                    frequencies.forEach(freq => {
                        const osc = audioContext.createOscillator();
                        osc.frequency.value = freq;
                        osc.type = "sine";
                        osc.connect(gainNode);
                        osc.start();
                        oscillators.push(osc);
                    });

                    // Ring pattern: 2 seconds on, 4 seconds off
                    setTimeout(() => {
                        oscillators.forEach(osc => osc.stop());
                    }, 2000);

                    // Repeat
                    ringtoneAudio = setTimeout(() => {
                        if (state.incomingCall) {
                            playRingTone();
                        }
                    }, 4000);
                }

                playRingTone();
            } catch (err) {
                console.warn("Could not play ringtone:", err);
            }
        }

        // Stop ringtone
        function stopRingtone() {
            if (ringtoneAudio) {
                clearTimeout(ringtoneAudio);
                ringtoneAudio = null;
            }
        }

        // Fallback beep sound using Web Audio API
        function playBeepSound() {
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();

                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);

                oscillator.frequency.value = 440;
                oscillator.type = "sine";
                gainNode.gain.value = 0.3;

                oscillator.start();

                // Beep pattern
                let beepCount = 0;
                const beepInterval = setInterval(() => {
                    if (beepCount >= 10 || !state.incomingCall) {
                        clearInterval(beepInterval);
                        oscillator.stop();
                        return;
                    }
                    gainNode.gain.value = gainNode.gain.value > 0 ? 0 : 0.3;
                    beepCount++;
                }, 500);
            } catch (err) {
                console.warn("Could not create beep sound:", err);
            }
        }

        // Show browser notification
        function showBrowserNotification(data) {
            if (!("Notification" in window)) return;

            if (Notification.permission === "granted") {
                createNotification(data);
            } else if (Notification.permission !== "denied") {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") {
                        createNotification(data);
                    }
                });
            }
        }

        function createNotification(data) {
            const title = data.partner?.name || data.phone_number || "Cuộc gọi đến";
            const options = {
                body: `Số: ${data.phone_number}`,
                icon: data.partner?.image || "/asterisk_connector/static/description/icon.png",
                tag: "incoming-call",
                requireInteraction: true,
            };

            const notification = new Notification(title, options);
            notification.onclick = () => {
                window.focus();
                notification.close();
            };
        }

        // Make call - phân tách theo loại: softphone (SIP) hoặc ipphone (AMI)
        async function makeCall(phoneNumber, callType = 'softphone') {
            console.log('[PhoneService] makeCall called:', {
                phoneNumber,
                callType,
                isConfigured: state.isConfigured,
                userConfig: state.userConfig
            });

            if (!state.isConfigured) {
                console.warn('[PhoneService] Not configured');
                notification.add("Bạn chưa được cấu hình extension Asterisk", {type: "warning"});
                return false;
            }

            // Kiểm tra trạng thái - chỉ ready mới được gọi
            console.log('[PhoneService] Status check:', state.userConfig?.status);
            if (state.userConfig?.status !== 'ready') {
                notification.add(`Bạn phải ở trạng thái Sẵn Sàng mới có thể gọi ra. Trạng thái hiện tại: ${state.userConfig?.status || 'offline'}`, {type: "warning"});
                return false;
            }

            // === CASE 1: SOFTPHONE - Gọi qua SIP/WebRTC ===
            if (callType === 'softphone') {
                console.log('[PhoneService] Softphone mode - using SIP/WebRTC');

                if (!isSIPRegistered()) {
                    notification.add("SIP client chưa kết nối. Vui lòng kiểm tra cấu hình WebRTC.", {type: "warning"});
                    return false;
                }

                try {
                    // Tạo call log trước khi gọi
                    let callLogId = null;
                    try {
                        const logResult = await rpc("/asterisk/log_softphone_call", {
                            phone_number: phoneNumber,
                            direction: 'outgoing',
                        });
                        if (logResult.success) {
                            callLogId = logResult.call_log_id;
                        }
                    } catch (err) {
                        console.error('[PhoneService] Error creating call log:', err);
                    }

                    const success = await makeSIPCall(phoneNumber, callLogId);
                    console.log('[PhoneService] WebRTC call result:', success);
                    if (success) {
                        state.activeCall = {
                            phoneNumber: phoneNumber,
                            direction: "outgoing",
                            state: "dialing",
                            startTime: new Date(),
                            callType: 'softphone',
                            callLogId: callLogId,
                            fromIPPhone: false,
                        };
                        notification.add(`Đang gọi tới ${phoneNumber} (Softphone)`, {type: "info"});
                        return true;
                    } else if (callLogId) {
                        // Gọi thất bại, cập nhật call log
                        rpc("/asterisk/update_call_log", {call_log_id: callLogId, state: 'failed'}).catch(e => console.error(e));
                    }
                } catch (error) {
                    console.error("WebRTC call error:", error);
                    notification.add("Lỗi khi gọi qua Softphone", {type: "danger"});
                    return false;
                }
                return false;
            }

            // === CASE 2: IPPHONE - Gọi qua AMI (không dùng WebRTC) ===
            if (callType === 'ipphone') {
                console.log('[PhoneService] IP Phone mode - using AMI');
                console.log('[PhoneService] RPC endpoint: /asterisk/make_call, phone:', phoneNumber);

                try {
                    console.log('[PhoneService] Calling RPC...');
                    const result = await rpc("/asterisk/make_call", {phone_number: phoneNumber});
                    console.log('[PhoneService] AMI call result:', result);
                    console.log('[PhoneService] AMI call result:', result);
                    if (result.success) {
                        state.activeCall = {
                            phoneNumber: phoneNumber,
                            direction: "outgoing",
                            state: "dialing",
                            startTime: new Date(),
                            callLogId: result.data?.call_log_id,
                            uniqueId: result.data?.unique_id,
                            channel: result.data?.result ? extractChannel(result.data.result) : null,
                            callType: 'ipphone',
                            fromIPPhone: true,
                        };
                        notification.add(`Đang gọi tới ${phoneNumber} (IP Phone)`, {type: "info"});
                        return true;
                    } else {
                        notification.add(result.error || "Không thể thực hiện cuộc gọi", {type: "danger"});
                        return false;
                    }
                } catch (error) {
                    console.error("Make call error:", error);
                    notification.add("Lỗi khi thực hiện cuộc gọi", {type: "danger"});
                    return false;
                }
            }

            // === CASE 3: BOTH - Thử WebRTC trước, nếu fail thì dùng AMI ===
            if (callType === 'both') {
                console.log('[PhoneService] Both mode - trying WebRTC first, then AMI fallback');

                // Thử WebRTC trước nếu SIP đã registered
                if (isSIPRegistered()) {
                    try {
                        // Tạo call log trước khi gọi
                        let callLogId = null;
                        try {
                            const logResult = await rpc("/asterisk/log_softphone_call", {
                                phone_number: phoneNumber,
                                direction: 'outgoing',
                            });
                            if (logResult.success) {
                                callLogId = logResult.call_log_id;
                            }
                        } catch (err) {
                            console.error('[PhoneService] Error creating call log:', err);
                        }

                        const success = await makeSIPCall(phoneNumber, callLogId);
                        if (success) {
                            state.activeCall = {
                                phoneNumber: phoneNumber,
                                direction: "outgoing",
                                state: "dialing",
                                startTime: new Date(),
                                callType: 'softphone',
                                callLogId: callLogId,
                                fromIPPhone: false,
                            };
                            notification.add(`Đang gọi tới ${phoneNumber} (Softphone)`, {type: "info"});
                            return true;
                        } else if (callLogId) {
                            rpc("/asterisk/update_call_log", {call_log_id: callLogId, state: 'failed'}).catch(e => console.error(e));
                        }
                    } catch (error) {
                        console.error("WebRTC call failed, will try AMI:", error);
                    }
                }

                // Fallback sang AMI
                console.log('[PhoneService] WebRTC failed or not available, falling back to AMI');
                try {
                    const result = await rpc("/asterisk/make_call", {phone_number: phoneNumber});
                    if (result.success) {
                        state.activeCall = {
                            phoneNumber: phoneNumber,
                            direction: "outgoing",
                            state: "dialing",
                            startTime: new Date(),
                            callLogId: result.data?.call_log_id,
                            uniqueId: result.data?.unique_id,
                            channel: result.data?.result ? extractChannel(result.data.result) : null,
                            callType: 'ipphone',
                            fromIPPhone: true,
                        };
                        notification.add(`Đang gọi tới ${phoneNumber} (IP Phone)`, {type: "info"});
                        return true;
                    } else {
                        notification.add(result.error || "Không thể thực hiện cuộc gọi", {type: "danger"});
                        return false;
                    }
                } catch (error) {
                    console.error("Make call error:", error);
                    notification.add("Lỗi khi thực hiện cuộc gọi", {type: "danger"});
                    return false;
                }
            }

            console.warn('[PhoneService] Unknown call type:', callType);
            return false;
        }

        // Helper to extract channel from AMI response
        function extractChannel(amiResponse) {
            // Try to extract channel from AMI response
            const match = amiResponse.match(/Channel:\s*(\S+)/i);
            return match ? match[1] : null;
        }

        // Answer call - phân tách theo call_type
        async function answerCall() {
            if (!state.incomingCall) return;

            const callType = state.incomingCall.callType || 'softphone';
            stopRingtone();

            // === CASE 1: SOFTPHONE hoặc BOTH - Trả lời qua SIP/WebRTC ===
            if ((callType === 'softphone' || callType === 'both') && hasSIPActiveCall()) {
                console.log('[PhoneService] Answering softphone call via SIP');
                const success = await acceptSIPCall();
                if (success) {
                    state.activeCall = {
                        ...state.incomingCall,
                        direction: "incoming",
                        state: "answered",
                        answerTime: new Date(),
                        callType: 'softphone',
                    };
                    state.incomingCall = null;
                    notification.add("Cuộc gọi đã được trả lời (Softphone)", {type: "success"});
                    return;
                }
            }

            // === CASE 2: IPPHONE - Chỉ cập nhật state (trả lời trên điện thoại IP) ===
            console.log('[PhoneService] IP Phone call - updating state only');
            state.activeCall = {
                ...state.incomingCall,
                direction: "incoming",
                state: "answered",
                answerTime: new Date(),
                callType: 'ipphone',
            };
            state.incomingCall = null;
            notification.add("Cuộc gọi đã được trả lời (IP Phone)", {type: "success"});
        }

        // Reject/Hangup call - phân tách theo call_type
        async function hangupCall(channel) {
            console.log("hangupCall called with channel:", channel);
            stopRingtone();

            const incomingCallType = state.incomingCall?.callType;
            const activeCallType = state.activeCall?.callType;


            // Check if this is rejecting an incoming call (before it's answered)
            if (state.incomingCall && !state.activeCall) {
                console.log("Rejecting incoming call, type:", incomingCallType);

                // === CASE 1: SOFTPHONE/BOTH - Reject qua SIP ===
                if ((incomingCallType === 'softphone' || incomingCallType === 'both') && hasSIPActiveCall()) {
                    rejectSIPCall();
                }
                // === CASE 2: IPPHONE - Không cần reject qua SIP (trả lời trên điện thoại IP) ===

                state.incomingCall = null;
                notification.add("Cuộc gọi đã bị từ chối", {type: "info"});
                return;
            }

            // === CASE 1: SOFTPHONE - Hangup qua SIP ===
            if (activeCallType === 'softphone' && hasSIPActiveCall()) {
                console.log("Hanging up softphone call via SIP");
                hangupSIPCall();  // cleanupSIPCall will store endedCall
                notification.add("Cuộc gọi đã kết thúc (Softphone)", {type: "info"});
                return;
            }

            // === CASE 2: IPPHONE - Hangup qua AMI ===
            const callChannel = channel || state.activeCall?.channel || state.incomingCall?.channel;
            console.log("AMI hangup for IP phone, channel:", callChannel);

            if (callChannel) {
                try {
                    const result = await rpc("/asterisk/hangup", {channel: callChannel});
                    console.log("Hangup result:", result);
                    if (!result.success) {
                        console.warn("Hangup API returned error:", result.error);
                    }
                } catch (error) {
                    console.error("Hangup RPC error:", error);
                }
            } else {
                console.log("No channel available for AMI hangup");
            }

            state.activeCall = null;
            state.incomingCall = null;
            notification.add("Cuộc gọi đã kết thúc (IP Phone)", {type: "info"});
        }

        // Transfer call
        async function transferCall(targetExtension) {
            if (!state.activeCall?.channel) {
                notification.add("Không có cuộc gọi đang hoạt động", {type: "warning"});
                return false;
            }

            try {
                const result = await rpc("/asterisk/transfer_call", {
                    channel: state.activeCall.channel,
                    target_extension: targetExtension,
                });

                if (result.success) {
                    notification.add(`Đã chuyển cuộc gọi tới ${targetExtension}`, {type: "success"});
                    state.activeCall = null;
                    return true;
                } else {
                    notification.add(result.error || "Không thể chuyển cuộc gọi", {type: "danger"});
                    return false;
                }
            } catch (error) {
                console.error("Transfer call error:", error);
                notification.add("Lỗi khi chuyển cuộc gọi", {type: "danger"});
                return false;
            }
        }

        // Hold call - phân tách theo call_type
        async function holdCall(hold = true) {
            if (!state.activeCall) {
                notification.add("Không có cuộc gọi đang hoạt động", {type: "warning"});
                return false;
            }

            const callType = state.activeCall?.callType;

            // === CASE 1: SOFTPHONE - Hold via SIP (TODO: implement) ===
            if (callType === 'softphone' && hasSIPActiveCall()) {
                // TODO: Implement SIP hold
                state.activeCall.isOnHold = hold;
                notification.add(hold ? "Cuộc gọi đã được giữ (Softphone)" : "Cuộc gọi đã được tiếp tục (Softphone)", {type: "info"});
                return true;
            }

            // === CASE 2: IPPHONE - Hold via AMI ===
            try {
                const result = await rpc("/asterisk/hold", {
                    channel: state.activeCall.channel,
                    hold: hold,
                });

                if (result.success) {
                    state.activeCall.isOnHold = hold;
                    notification.add(hold ? "Cuộc gọi đã được giữ (IP Phone)" : "Cuộc gọi đã được tiếp tục (IP Phone)", {type: "info"});
                    return true;
                } else {
                    notification.add(result.error || "Không thể giữ cuộc gọi", {type: "danger"});
                    return false;
                }
            } catch (error) {
                console.error("Hold call error:", error);
                notification.add("Lỗi khi giữ cuộc gọi", {type: "danger"});
                return false;
            }
        }

        // Mute call - phân tách theo call_type
        async function muteCall(mute = true) {
            if (!state.activeCall) {
                notification.add("Không có cuộc gọi đang hoạt động", {type: "warning"});
                return false;
            }

            const callType = state.activeCall?.callType;

            // === CASE 1: SOFTPHONE - Mute via SIP ===
            if (callType === 'softphone' && hasSIPActiveCall()) {
                try {
                    setSIPMute(mute);
                    state.activeCall.isMuted = mute;
                    notification.add(mute ? "Micro đã tắt (Softphone)" : "Micro đã bật (Softphone)", {type: "info"});
                    return true;
                } catch (error) {
                    console.error("WebRTC mute error:", error);
                }
            }

            // === CASE 2: IPPHONE - Mute via AMI ===
            if (state.activeCall.channel) {
                try {
                    const result = await rpc("/asterisk/mute", {
                        channel: state.activeCall.channel,
                        mute: mute,
                    });

                    if (result.success) {
                        state.activeCall.isMuted = mute;
                        notification.add(mute ? "Micro đã tắt (IP Phone)" : "Micro đã bật (IP Phone)", {type: "info"});
                        return true;
                    } else {
                        notification.add(result.error || "Không thể tắt tiếng", {type: "danger"});
                        return false;
                    }
                } catch (error) {
                    console.error("Mute call error:", error);
                    notification.add("Lỗi khi tắt tiếng", {type: "danger"});
                    return false;
                }
            }

            // Fallback: just update state
            state.activeCall.isMuted = mute;
            return true;
        }

        // Send DTMF tone during call - phân tách theo call_type
        function sendDTMF(digit) {
            if (!state.activeCall) {
                return false;
            }

            const callType = state.activeCall?.callType;

            // === CASE 1: SOFTPHONE - Send DTMF via SIP ===
            if (callType === 'softphone' && hasSIPActiveCall()) {
                try {
                    sendSIPDTMF(digit);
                    console.log("DTMF sent via SIP:", digit);
                    return true;
                } catch (error) {
                    console.error("WebRTC DTMF error:", error);
                }
            }

            // === CASE 2: IPPHONE - Không gửi DTMF qua SIP (điện thoại IP tự xử lý) ===
            console.log("DTMF for IP phone (not sent via SIP):", digit);
            return true;
        }

        // Load call history
        async function loadCallHistory(limit = 100) {
            try {
                const result = await rpc("/asterisk/get_call_history", {limit});
                if (result.success) {
                    state.callHistory = result.data;
                }
            } catch (error) {
                console.error("Load call history error:", error);
            }
        }

        // Load extensions for transfer
        async function loadExtensions() {
            try {
                const result = await rpc("/asterisk/get_extensions");
                if (result.success) {
                    state.extensions = result.data;
                }
            } catch (error) {
                console.error("Load extensions error:", error);
            }
        }

        // Load user's available extensions for settings
        async function loadUserExtensions() {
            try {
                const result = await rpc("/asterisk/get_user_extensions");
                if (result.success) {
                    return result.data;
                }
            } catch (error) {
                console.error("Load user extensions error:", error);
            }
            return [];
        }

        // Save user settings (extension, preferred call type)
        async function saveUserSettings(settings) {
            try {
                const result = await rpc("/asterisk/save_user_settings", {settings});
                if (result.success) {
                    return true;
                } else {
                    console.error("Save settings error:", result.error);
                }
            } catch (error) {
                console.error("Save user settings error:", error);
            }
            return false;
        }

        // Reload user config after settings change
        async function reloadUserConfig() {
            await loadUserConfig();
        }

        // Update user status in state (called when status changes in systray)
        function updateUserStatus(newStatus) {
            if (state.userConfig) {
                state.userConfig.status = newStatus;
                console.log('[PhoneService] User status updated to:', newStatus);
            }
        }

        // Search partner by phone
        async function searchPartner(phoneNumber) {
            try {
                const result = await rpc("/asterisk/search_partner", {phone_number: phoneNumber});
                if (result.success) {
                    return result.data;
                }
            } catch (error) {
                console.error("Search partner error:", error);
            }
            return [];
        }

        // Dismiss incoming call (for ipphone mode - just clear notification)
        function dismissIncomingCall() {
            stopRingtone();
            state.incomingCall = null;
        }

        // Toggle widget
        function toggleWidget() {
            state.isWidgetOpen = !state.isWidgetOpen;
            if (state.isWidgetOpen && state.callHistory.length === 0) {
                loadCallHistory();
            }
        }

        // Load CRM tags for care note popup
        async function loadCrmTags() {
            try {
                const result = await rpc("/asterisk/get_crm_tags");
                if (result.success) {
                    state.crmTags = result.data || [];
                }
            } catch (error) {
                console.error('[PhoneService] Load CRM tags error:', error);
            }
        }

        // Save care note (called during/after active call)
        async function saveCareNote(callLogId, note, tagIds, callResult, direction) {
            try {
                const result = await rpc("/asterisk/save_care_note", {
                    call_log_id: callLogId,
                    note: note || '',
                    tag_ids: tagIds || [],
                    call_result: callResult || '',
                    call_type: direction || 'outgoing',
                });
                if (result.success) {
                    notification.add('Đã lưu ghi chú cuộc gọi', {type: 'success'});
                    return true;
                } else {
                    notification.add(result.error || 'Không thể lưu ghi chú', {type: 'danger'});
                    return false;
                }
            } catch (error) {
                console.error('[PhoneService] Save care note error:', error);
                notification.add('Lỗi khi lưu ghi chú', {type: 'danger'});
                return false;
            }
        }

        // Dismiss care note popup without saving (kept for compatibility)
        function dismissCareNote() {
            state.endedCall = null;
        }

        // Format duration
        function formatDuration(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
        }

        // Test incoming call (for debugging)
        async function testIncomingCall(phoneNumber = '0123456789') {
            try {
                const result = await rpc("/asterisk/test_incoming_call", {phone_number: phoneNumber});
                console.log("Test incoming call result:", result);
                return result;
            } catch (error) {
                console.error("Test incoming call error:", error);
            }
        }


        // Initialize
        loadUserConfig();

        return {
            state,
            notification,
            makeCall,
            answerCall,
            hangupCall,
            transferCall,
            holdCall,
            muteCall,
            sendDTMF,
            loadCallHistory,
            loadExtensions,
            loadUserExtensions,
            saveUserSettings,
            reloadUserConfig,
            updateUserStatus,
            searchPartner,
            toggleWidget,
            stopRingtone,
            dismissIncomingCall,
            formatDuration,
            testIncomingCall,
            loadCrmTags,
            saveCareNote,
            dismissCareNote,
        };
    },
};

registry.category("services").add("asterisk_phone", asteriskPhoneService);
