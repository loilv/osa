# -*- coding: utf-8 -*-

import json
import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class AsteriskController(http.Controller):

    @http.route('/asterisk/make_call', type='jsonrpc', auth='user')
    def make_call(self, phone_number, **kwargs):
        """API endpoint để thực hiện cuộc gọi"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'Chưa cấu hình extension Asterisk'}
        
        try:
            result = asterisk_user.make_call(phone_number)
            return {'success': True, 'data': result}
        except Exception as e:
            _logger.error('Make call error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/transfer_call', type='jsonrpc', auth='user')
    def transfer_call(self, channel, target_extension, **kwargs):
        """API endpoint để chuyển cuộc gọi"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'Chưa cấu hình extension Asterisk'}
        
        try:
            result = asterisk_user.transfer_call(channel, target_extension)
            return {'success': True, 'data': result}
        except Exception as e:
            _logger.error('Transfer call error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/hangup', type='jsonrpc', auth='user')
    def hangup(self, channel, **kwargs):
        """API endpoint để kết thúc cuộc gọi"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'Chưa cấu hình extension Asterisk'}
        
        try:
            result = asterisk_user.hangup(channel)
            return {'success': True, 'data': result}
        except Exception as e:
            _logger.error('Hangup error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/hold', type='jsonrpc', auth='user')
    def hold_call(self, channel, hold=True, **kwargs):
        """API endpoint để hold/unhold cuộc gọi"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'Chưa cấu hình extension Asterisk'}
        
        try:
            result = asterisk_user.hold_call(channel, hold)
            return {'success': True, 'data': result}
        except Exception as e:
            _logger.error('Hold call error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/mute', type='jsonrpc', auth='user')
    def mute_call(self, channel, mute=True, **kwargs):
        """API endpoint để mute/unmute cuộc gọi"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'Chưa cấu hình extension Asterisk'}
        
        try:
            result = asterisk_user.mute_call(channel, mute)
            return {'success': True, 'data': result}
        except Exception as e:
            _logger.error('Mute call error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/get_user_config', type='jsonrpc', auth='user')
    def get_user_config(self, **kwargs):
        """Lấy cấu hình Asterisk của user hiện tại"""
        config = request.env['asterisk.user'].get_current_user_asterisk()
        _logger.info('User config for WebRTC: ws_enabled=%s, has_sip_password=%s, ws_url=%s',
                     config.get('ws_enabled'), bool(config.get('sip_password')), config.get('ws_url'))
        return {'success': True, 'data': config}

    @http.route('/asterisk/events', type='http', auth='none', csrf=False, methods=['POST'])
    def ami_events_http(self, **kwargs):
        """
        HTTP endpoint nhận event từ AMI Listener service.
        Accepts plain JSON POST: {"event": "...", "data": {...}}
        """
        try:
            body = json.loads(request.httprequest.data)
        except (json.JSONDecodeError, TypeError):
            return request.make_json_response({'success': False, 'error': 'Invalid JSON'}, status=400)

        event_type = body.get('event')
        event_data = body.get('data', {})

        if not event_type:
            return request.make_json_response({'success': False, 'error': 'Missing event type'}, status=400)

        _logger.info('AMI Event [%s] received via HTTP | UniqueID: %s',
                     event_type, event_data.get('Uniqueid', ''))

        try:
            self._dispatch_ami_event(event_type, event_data)
            return request.make_json_response({'success': True})
        except Exception as e:
            _logger.error('AMI Event [%s] error: %s', event_type, str(e), exc_info=True)
            return request.make_json_response({'success': False, 'error': str(e)}, status=500)

    @http.route('/asterisk/ami_event', type='jsonrpc', auth='none', csrf=False)
    def ami_event(self, **kwargs):
        """
        JSON-RPC endpoint nhận event từ Asterisk AMI (legacy).
        """
        _logger.info('AMI Event received: %s', kwargs.get('event', ''))
        event_type = kwargs.get('event')
        try:
            self._dispatch_ami_event(event_type, kwargs)
            return {'success': True}
        except Exception as e:
            _logger.error('AMI Event error: %s', str(e))
            return {'success': False, 'error': str(e)}

    def _dispatch_ami_event(self, event_type, data):
        """Dispatch AMI event to appropriate handler"""
        if event_type == 'Newchannel':
            self._handle_newchannel_event(data)
        elif event_type == 'Dial':
            self._handle_dial_event(data)
        elif event_type == 'Ringing':
            self._handle_ringing_event(data)
        elif event_type == 'Answer':
            self._handle_answer_event(data)
        elif event_type == 'Hangup':
            self._handle_hangup_event(data)
        elif event_type == 'Transfer':
            self._handle_transfer_event(data)
        elif event_type == 'Cdr':
            self._handle_cdr_event(data)
        elif event_type == 'Newexten':
            self._handle_newexten_event(data)

    def _handle_ringing_event(self, data):
        """Xử lý event đổ chuông - cuộc gọi đến"""
        with request.env.cr.savepoint():
            call_log = request.env['asterisk.call.log'].sudo().create_incoming_call({
                'caller_id_num': data.get('CallerIDNum'),
                'caller_id_name': data.get('CallerIDName'),
                'extension': data.get('Exten') or data.get('ConnectedLineNum'),
                'channel': data.get('Channel'),
                'unique_id': data.get('Uniqueid'),
                'linked_id': data.get('Linkedid'),
            })
            
            # Gửi notification tới user qua bus
            if call_log and call_log.asterisk_user_id:
                self._notify_incoming_call(call_log)

    def _handle_answer_event(self, data):
        """Xử lý event trả lời cuộc gọi"""
        with request.env.cr.savepoint():
            request.env['asterisk.call.log'].sudo().update_call_state(
                data.get('Uniqueid'),
                'answered'
            )

    def _handle_hangup_event(self, data):
        """Xử lý event kết thúc cuộc gọi"""
        cause = data.get('Cause', '0')
        state = 'hangup'
        
        if cause == '17':
            state = 'busy'
        elif cause == '19':
            state = 'no_answer'
        elif cause not in ('0', '16'):
            state = 'failed'
        
        with request.env.cr.savepoint():
            call_log = request.env['asterisk.call.log'].sudo().update_call_state(
                data.get('Uniqueid'),
                state,
                billsec=data.get('BillableSeconds', 0)
            )
            
            # Tự động tạo crm.lead.care.history cho cuộc gọi đã kết nối
            if call_log and call_log.answer_time:
                self._auto_create_care_history(call_log)

    def _handle_transfer_event(self, data):
        """Xử lý event chuyển cuộc gọi"""
        with request.env.cr.savepoint():
            call_log = request.env['asterisk.call.log'].sudo().search([
                ('unique_id', '=', data.get('Uniqueid'))
            ], limit=1)
            
            if call_log:
                call_log.write({
                    'state': 'transferred',
                    'transfer_to': data.get('TransferTarget'),
                })

    def _handle_newchannel_event(self, data):
        """Xử lý event khi có channel mới - đặc biệt cho cuộc gọi đi từ IP phone"""
        channel = data.get('Channel', '')
        context = data.get('Context', '')
        exten = data.get('Exten', '')
        unique_id = data.get('Uniqueid', '')
        caller_id_num = data.get('CallerIDNum', '')
        
        # Chỉ xử lý nếu là cuộc gọi đi (from-internal context)
        if 'from-internal' not in context:
            return
        
        # Tìm asterisk user từ channel
        # Channel thường có dạng: PJSIP/100-00000001
        extension = None
        for prefix in ['PJSIP/', 'SIP/', 'IAX2/', 'DAHDI/']:
            if channel.startswith(prefix):
                ext_part = channel[len(prefix):]
                extension = ext_part.split('-')[0]
                break
        
        if not extension:
            return
        
        with request.env.cr.savepoint():
            asterisk_user = request.env['asterisk.user'].sudo().search([
                ('extension', '=', extension),
            ], limit=1)
            
            if asterisk_user and exten and exten not in ['s', 'h']:
                # Kiểm tra xem đã có call log cho unique_id này chưa
                existing = request.env['asterisk.call.log'].sudo().search([
                    ('unique_id', '=', unique_id)
                ], limit=1)
                
                if not existing:
                    # Tạo call log cho cuộc gọi đi từ IP phone
                    call_log = request.env['asterisk.call.log'].sudo().create({
                        'asterisk_user_id': asterisk_user.id,
                        'direction': 'outgoing',
                        'phone_number': exten,
                        'channel': channel,
                        'unique_id': unique_id,
                        'state': 'dialing',
                    })
                    _logger.info('Created outgoing call log for IP phone: %s -> %s', extension, exten)
                    
                    # Gửi thông báo tới user về cuộc gọi đi
                    self._notify_outgoing_call(call_log)

    def _handle_dial_event(self, data):
        """Xử lý event Dial - khi IP phone bắt đầu quay số"""
        channel = data.get('Channel', '')
        dest_channel = data.get('DestChannel', '')
        unique_id = data.get('Uniqueid', '')
        dial_string = data.get('DialString', '')
        
        with request.env.cr.savepoint():
            # Cập nhật call log nếu đã có
            call_log = request.env['asterisk.call.log'].sudo().search([
                ('unique_id', '=', unique_id)
            ], limit=1)
            
            if call_log:
                call_log.write({
                    'state': 'ringing',
                })

    def _handle_newexten_event(self, data):
        """Xử lý event Newexten - lấy recording URL từ MixMonitor"""
        if data.get('Application') != 'MixMonitor':
            return

        unique_id = data.get('Uniqueid', '')
        linked_id = data.get('Linkedid', '')
        app_data = data.get('AppData', '')

        # AppData format: /path/to/recording.wav,options
        recording_file = app_data.split(',')[0] if app_data else ''
        if not recording_file:
            return

        # Tìm call log theo unique_id hoặc linked_id
        lookup_id = linked_id or unique_id
        if not lookup_id:
            return

        with request.env.cr.savepoint():
            call_log = request.env['asterisk.call.log'].sudo().search([
                '|',
                ('unique_id', '=', lookup_id),
                ('linked_id', '=', lookup_id),
            ], limit=1)

            if call_log:
                # Xây dựng URL ghi âm
                recording_url = self._build_recording_url(recording_file)
                call_log.write({'recording_url': recording_url})
                _logger.info('Recording URL saved for call %s: %s', lookup_id, recording_url)

    def _handle_cdr_event(self, data):
        """Xử lý event CDR - cập nhật thông tin cuộc gọi cuối cùng"""
        unique_id = data.get('Uniqueid', '')
        linked_id = data.get('Linkedid', '')
        if not unique_id:
            return

        # Skip noise: Local channel, voicebot, etc.
        channel = data.get('Channel', '')
        if channel.startswith('Local/') and data.get('Disposition') == 'NO ANSWER':
            return

        lookup_id = linked_id if linked_id and unique_id == linked_id else unique_id

        with request.env.cr.savepoint():
            call_log = request.env['asterisk.call.log'].sudo().search([
                '|',
                ('unique_id', '=', lookup_id),
                ('linked_id', '=', lookup_id),
            ], limit=1, order='id desc')

            if not call_log:
                return

            vals = {}
            # Cập nhật billsec
            billsec = data.get('BillableSeconds') or data.get('Billsec')
            if billsec:
                vals['billsec'] = int(billsec)

            # Cập nhật duration
            duration = data.get('Duration')
            if duration:
                vals['duration'] = int(duration)

            # Cập nhật thời gian
            if data.get('StartTime'):
                try:
                    vals['start_time'] = fields.Datetime.to_datetime(data['StartTime'])
                except Exception:
                    pass
            if data.get('EndTime'):
                try:
                    vals['end_time'] = fields.Datetime.to_datetime(data['EndTime'])
                except Exception:
                    vals['end_time'] = fields.Datetime.now()
            if data.get('AnswerTime') and not call_log.answer_time:
                try:
                    vals['answer_time'] = fields.Datetime.to_datetime(data['AnswerTime'])
                except Exception:
                    pass

            # Recording từ CDR nếu chưa có
            if not call_log.recording_url:
                rec_file = data.get('RecordingFile', '')
                if rec_file:
                    vals['recording_url'] = self._build_recording_url(rec_file)

            # Cập nhật state từ Disposition
            disposition = data.get('Disposition', '')
            if disposition == 'ANSWERED' and call_log.state not in ('hangup',):
                if not call_log.answer_time:
                    vals['state'] = 'answered'
            elif disposition == 'NO ANSWER':
                vals['state'] = 'no_answer'
            elif disposition == 'BUSY':
                vals['state'] = 'busy'
            elif disposition == 'FAILED':
                vals['state'] = 'failed'

            if vals:
                call_log.write(vals)
                _logger.info('CDR updated call log %s: %s', call_log.id, list(vals.keys()))

    def _build_recording_url(self, recording_path):
        """Xây dựng URL đầy đủ cho file ghi âm"""
        if not recording_path:
            return ''

        # Nếu đã là URL đầy đủ
        if recording_path.startswith(('http://', 'https://')):
            return recording_path

        # Lấy recording base URL từ server config
        server = request.env['asterisk.server'].sudo().search([
            ('active', '=', True),
        ], limit=1)

        base_url = ''
        if server and server.recording_base_url:
            base_url = server.recording_base_url.rstrip('/')

        # Lấy tên file từ đường dẫn đầy đủ
        filename = recording_path.split('/')[-1] if '/' in recording_path else recording_path

        if base_url:
            return f"{base_url}/{filename}"
        return recording_path

    def _auto_create_care_history(self, call_log):
        """Tự động tạo crm.lead.care.history khi cuộc gọi kết thúc (đã kết nối)"""
        try:
            # Kiểm tra model tồn tại (telesale_crm có thể chưa cài)
            if 'crm.lead.care.history' not in request.env:
                return

            CareHistory = request.env['crm.lead.care.history'].sudo()

            # Kiểm tra đã tạo care history cho call_log này chưa
            existing = CareHistory.search([('call_log_id', '=', call_log.id)], limit=1)
            if existing:
                return

            call_type = 'out' if call_log.direction == 'outgoing' else 'in'

            vals = {
                'call_log_id': call_log.id,
                'call_type': call_type,
                'user_id': call_log.user_id.id if call_log.user_id else False,
                'record_url': call_log.recording_url or '',
                'note': '',
            }

            # Tự động liên kết với lead nếu có partner
            if call_log.partner_id and 'crm.lead' in request.env:
                lead = request.env['crm.lead'].sudo().search([
                    ('partner_id', '=', call_log.partner_id.id),
                    ('active', '=', True),
                ], limit=1, order='create_date desc')
                if lead:
                    vals['lead_id'] = lead.id

            CareHistory.create(vals)
            _logger.info('Auto-created care history for call_log %s (direction=%s, phone=%s)',
                         call_log.id, call_log.direction, call_log.phone_number)
        except Exception as e:
            _logger.error('Error auto-creating care history for call_log %s: %s',
                          call_log.id, str(e))

    def _notify_outgoing_call(self, call_log):
        """Gửi notification tới user về cuộc gọi đi (từ IP phone)"""
        if not call_log.asterisk_user_id:
            return
        
        channel = f'asterisk_call_{call_log.asterisk_user_id.user_id.id}'
        
        partner_info = {}
        if call_log.partner_id:
            partner_info = {
                'id': call_log.partner_id.id,
                'name': call_log.partner_id.name,
                'email': call_log.partner_id.email,
                'phone': call_log.partner_id.phone,
                'image': f'/web/image/res.partner/{call_log.partner_id.id}/avatar_128',
            }
        
        message = {
            'type': 'outgoing_call',
            'call_log_id': call_log.id,
            'phone_number': call_log.phone_number,
            'channel': call_log.channel,
            'unique_id': call_log.unique_id,
            'partner': partner_info,
            'start_time': call_log.start_time.isoformat() if call_log.start_time else None,
        }
        
        _logger.info('[Asterisk] Sending outgoing_call to channel: %s, user_id: %s', channel, call_log.asterisk_user_id.user_id.id)
        request.env['bus.bus']._sendone(channel, 'asterisk/outgoing_call', message)

    def _notify_incoming_call(self, call_log):
        """Gửi notification tới user về cuộc gọi đến - chỉ khi agent online"""
        # Kiểm tra agent có online không - chỉ online mới nhận được cuộc gọi
        if call_log.asterisk_user_id.status != 'online':
            _logger.info('[Asterisk] Agent %s is not online (status: %s), skipping incoming call notification',
                        call_log.asterisk_user_id.extension, call_log.asterisk_user_id.status)
            return
        
        channel = f'asterisk_call_{call_log.asterisk_user_id.user_id.id}'
        
        partner_info = {}
        if call_log.partner_id:
            partner_info = {
                'id': call_log.partner_id.id,
                'name': call_log.partner_id.name,
                'email': call_log.partner_id.email,
                'phone': call_log.partner_id.phone,
                'image': f'/web/image/res.partner/{call_log.partner_id.id}/avatar_128',
            }
        
        message = {
            'type': 'incoming_call',
            'call_log_id': call_log.id,
            'phone_number': call_log.phone_number,
            'caller_id': call_log.caller_id,
            'channel': call_log.channel,
            'unique_id': call_log.unique_id,
            'partner': partner_info,
            'start_time': call_log.start_time.isoformat() if call_log.start_time else None,
        }
        
        _logger.info('[Asterisk] Sending incoming_call to channel: %s, user_id: %s', channel, call_log.asterisk_user_id.user_id.id)
        request.env['bus.bus']._sendone(channel, 'asterisk/incoming_call', message)

    @http.route('/asterisk/get_call_history', type='jsonrpc', auth='user')
    def get_call_history(self, limit=100, offset=0, **kwargs):
        """Lấy lịch sử 100 cuộc gọi gần nhất của extension được chọn"""
        asterisk_user = request.env['asterisk.user'].sudo().search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'Chưa cấu hình extension'}
        
        call_logs = request.env['asterisk.call.log'].sudo().search([
            ('asterisk_user_id', '=', asterisk_user.id)
        ], limit=limit, offset=offset, order='start_time desc')
        
        data = []
        for log in call_logs:
            data.append({
                'id': log.id,
                'direction': log.direction,
                'phone_number': log.phone_number,
                'caller_id': log.caller_id or '',
                'partner_id': log.partner_id.id if log.partner_id else False,
                'partner_name': log.partner_id.name if log.partner_id else '',
                'state': log.state,
                'duration': log.duration,
                'duration_display': log.duration_display,
                'start_time': fields.Datetime.to_string(log.start_time) if log.start_time else None,
                'answer_time': fields.Datetime.to_string(log.answer_time) if log.answer_time else None,
                'end_time': fields.Datetime.to_string(log.end_time) if log.end_time else None,
            })
        
        return {
            'success': True,
            'data': data,
            'extension': asterisk_user.extension,
            'total': request.env['asterisk.call.log'].sudo().search_count([
                ('asterisk_user_id', '=', asterisk_user.id)
            ]),
        }

    @http.route('/asterisk/search_partner', type='jsonrpc', auth='user')
    def search_partner(self, phone_number, **kwargs):
        """Tìm kiếm partner theo số điện thoại"""
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        partners = request.env['res.partner'].search([
            '|',
            ('phone', 'ilike', clean_number[-9:]),
            ('phone', 'ilike', phone_number),
        ], limit=5)
        
        data = []
        for partner in partners:
            data.append({
                'id': partner.id,
                'name': partner.name,
                'phone': partner.phone,
                'email': partner.email,
                'image': f'/web/image/res.partner/{partner.id}/avatar_128',
            })
        
        return {'success': True, 'data': data}

    @http.route('/asterisk/get_extensions', type='jsonrpc', auth='user')
    def get_extensions(self, **kwargs):
        """Lấy danh sách extension để chuyển cuộc gọi"""
        extensions = request.env['asterisk.user'].search([
            ('active', '=', True),
            ('user_id', '!=', request.env.uid),
        ])
        
        data = []
        for ext in extensions:
            data.append({
                'id': ext.id,
                'extension': ext.extension,
                'user_name': ext.user_id.name,
                'channel': ext.channel,
            })
        
        return {'success': True, 'data': data}

    @http.route('/asterisk/get_user_extensions', type='jsonrpc', auth='user')
    def get_user_extensions(self, **kwargs):
        """Lấy danh sách extension cho user - từ AMI hoặc database"""
        # Kiểm tra nếu có server được cấu hình
        servers = request.env['asterisk.server'].search([('active', '=', True)])
        
        if servers:
            # Thử lấy từ AMI trước
            all_extensions = []
            for server in servers:
                try:
                    extensions = server.get_extensions_from_ami()
                    if extensions:
                        all_extensions.extend(extensions)
                except Exception as e:
                    _logger.error('Error getting extensions from server %s: %s', server.name, str(e))
            
            if all_extensions:
                return {'success': True, 'data': all_extensions, 'source': 'ami'}
        
        # Fallback: lấy từ database
        user_extensions = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ])
        
        if user_extensions:
            data = []
            for user in user_extensions:
                data.append({
                    'id': user.id,
                    'extension': user.extension,
                    'server_name': user.server_id.name,
                    'server_host': user.server_id.host,
                    'channel': user.channel,
                    'call_type': user.call_type,
                })
            return {'success': True, 'data': data, 'source': 'database'}
        
        # Nếu user chưa có extension - trả về tất cả extensions từ database
        all_extensions_db = request.env['asterisk.user'].search([
            ('active', '=', True),
        ])
        data = []
        for ext in all_extensions_db:
            data.append({
                'id': ext.id,
                'extension': ext.extension,
                'server_name': ext.server_id.name,
                'server_host': ext.server_id.host,
                'channel': ext.channel,
                'call_type': ext.call_type,
                'user_name': ext.user_id.name if ext.user_id else 'Chưa gán',
            })
        return {'success': True, 'data': data, 'source': 'database', 'unassigned': True}

    @http.route('/asterisk/save_user_settings', type='jsonrpc', auth='user')
    def save_user_settings(self, settings=None, **kwargs):
        """Lưu cấu hình vào model asterisk.user - tạo hoặc cập nhật record"""
        if not settings:
            return {'success': False, 'error': 'No settings provided'}
        
        try:
            extension = settings.get('extension')
            preferred_call_type = settings.get('preferred_call_type', 'softphone')
            
            if not extension:
                return {'success': False, 'error': 'Extension is required'}
            
            # Tìm extension trong hệ thống
            asterisk_user = request.env['asterisk.user'].search([
                ('extension', '=', extension),
                ('active', '=', True),
            ], limit=1)
            
            if asterisk_user:
                # Cập nhật user cho extension này
                asterisk_user.sudo().write({
                    'user_id': request.env.uid,
                    'call_type': preferred_call_type,
                })
            else:
                # Tạo mới nếu extension từ AMI chưa có trong DB
                # Tìm server đầu tiên để gán
                server = request.env['asterisk.server'].search([
                    ('active', '=', True),
                ], limit=1)
                
                if not server:
                    return {'success': False, 'error': 'No active Asterisk server found'}
                
                asterisk_user = request.env['asterisk.user'].sudo().create({
                    'user_id': request.env.uid,
                    'server_id': server.id,
                    'extension': extension,
                    'call_type': preferred_call_type,
                    'channel_type': 'PJSIP',
                })
            
            return {'success': True, 'asterisk_user_id': asterisk_user.id}
            
        except Exception as e:
            _logger.error('Error saving user settings: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/test_incoming_call', type='jsonrpc', auth='user')
    def test_incoming_call(self, phone_number='0123456789', **kwargs):
        """Test endpoint to simulate an incoming call notification"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'No asterisk user configured'}
        
        # Create a test call log
        call_log = request.env['asterisk.call.log'].sudo().create({
            'asterisk_user_id': asterisk_user.id,
            'direction': 'incoming',
            'phone_number': phone_number,
            'caller_id': phone_number,
            'channel': f'PJSIP/{asterisk_user.extension}-test',
            'unique_id': f'test-{fields.Datetime.now().timestamp()}',
            'state': 'ringing',
        })
        
        # Send notification via bus
        channel = f'asterisk_call_{request.env.uid}'
        message = {
            'type': 'incoming_call',
            'call_log_id': call_log.id,
            'phone_number': phone_number,
            'caller_id': phone_number,
            'channel': call_log.channel,
            'unique_id': call_log.unique_id,
            'partner': None,
            'start_time': call_log.start_time.isoformat() if call_log.start_time else None,
        }
        
        request.env['bus.bus']._sendone(channel, 'asterisk/incoming_call', message)
        _logger.info('Test incoming call notification sent to channel: %s', channel)
        
        return {'success': True, 'data': message}

    @http.route('/asterisk/answer_call', type='jsonrpc', auth='user')
    def answer_call(self, unique_id=None, call_log_id=None, **kwargs):
        """API endpoint để trả lời cuộc gọi (cho IP phone hoặc softphone)"""
        call_log = None
        if call_log_id:
            call_log = request.env['asterisk.call.log'].sudo().browse(call_log_id)
            if not call_log.exists():
                call_log = None
        if not call_log and unique_id:
            call_log = request.env['asterisk.call.log'].sudo().search([
                ('unique_id', '=', unique_id)
            ], limit=1)
        
        if call_log:
            call_log.write({
                'state': 'answered',
                'answer_time': fields.Datetime.now(),
            })
        
        return {'success': True}

    @http.route('/asterisk/log_softphone_call', type='jsonrpc', auth='user')
    def log_softphone_call(self, phone_number, direction='outgoing', caller_id=None, **kwargs):
        """Tạo call log cho cuộc gọi softphone (WebRTC) - không qua AMI"""
        asterisk_user = request.env['asterisk.user'].search([
            ('user_id', '=', request.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {'success': False, 'error': 'No asterisk user configured'}
        
        try:
            call_log = request.env['asterisk.call.log'].sudo().create({
                'asterisk_user_id': asterisk_user.id,
                'direction': direction,
                'phone_number': phone_number,
                'caller_id': caller_id or phone_number,
                'state': 'dialing' if direction == 'outgoing' else 'ringing',
            })
            
            return {
                'success': True,
                'call_log_id': call_log.id,
            }
        except Exception as e:
            _logger.error('Error creating softphone call log: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/update_call_log', type='jsonrpc', auth='user')
    def update_call_log(self, call_log_id, state, **kwargs):
        """Cập nhật trạng thái call log (cho softphone)"""
        if not call_log_id:
            return {'success': False, 'error': 'call_log_id is required'}
        
        try:
            call_log = request.env['asterisk.call.log'].sudo().browse(call_log_id)
            if not call_log.exists():
                return {'success': False, 'error': 'Call log not found'}
            
            vals = {'state': state}
            if state == 'answered' and not call_log.answer_time:
                vals['answer_time'] = fields.Datetime.now()
            elif state in ('hangup', 'no_answer', 'busy', 'failed'):
                vals['end_time'] = fields.Datetime.now()
            
            call_log.write(vals)
            return {'success': True}
        except Exception as e:
            _logger.error('Error updating call log: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/update_status', type='jsonrpc', auth='user')
    def update_status(self, status=None, reason=None, **kwargs):
        """API endpoint để cập nhật trạng thái agent và tạo log"""
        if not status:
            return {'success': False, 'error': 'Status is required'}
        
        try:
            # Tìm asterisk user của current user
            asterisk_user = request.env['asterisk.user'].search([
                ('user_id', '=', request.env.uid),
                ('active', '=', True),
            ], limit=1)
            
            if not asterisk_user:
                return {'success': False, 'error': 'No asterisk user configured'}
            
            # Gọi method update_status
            result = asterisk_user.update_status(status, reason)
            return result
            
        except Exception as e:
            _logger.error('Error updating status: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/get_crm_tags', type='jsonrpc', auth='user')
    def get_crm_tags(self, **kwargs):
        """Lấy danh sách CRM tags để chọn khi lưu ghi chú cuộc gọi"""
        try:
            tags = request.env['crm.tag'].search([])
            data = [{'id': t.id, 'name': t.name} for t in tags]
            return {'success': True, 'data': data}
        except Exception as e:
            _logger.error('Error getting CRM tags: %s', str(e))
            return {'success': False, 'error': str(e), 'data': []}

    @http.route('/asterisk/save_care_note', type='jsonrpc', auth='user')
    def save_care_note(self, call_log_id=None, note=None, tag_id=None, call_type=None, **kwargs):
        """Lưu ghi chú cuộc gọi vào crm.lead.care.history"""
        try:
            vals = {
                'note': note or '',
                'user_id': request.env.uid,
                'call_type': 'out' if call_type == 'outgoing' else 'in',
            }

            if tag_id:
                vals['tag_ids'] = [(4, int(tag_id))]

            if call_log_id:
                call_log = request.env['asterisk.call.log'].sudo().browse(int(call_log_id))
                if call_log.exists():
                    vals['call_log_id'] = call_log.id
                    # Tự động liên kết với lead nếu có partner và partner có lead
                    if call_log.partner_id:
                        lead = request.env['crm.lead'].search([
                            ('partner_id', '=', call_log.partner_id.id),
                            ('active', '=', True),
                        ], limit=1, order='create_date desc')
                        if lead:
                            vals['lead_id'] = lead.id

            care_history = request.env['crm.lead.care.history'].sudo().create(vals)
            return {'success': True, 'id': care_history.id}
        except Exception as e:
            _logger.error('Error saving care note: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/asterisk/get_agent_status', type='jsonrpc', auth='user')
    def get_agent_status(self, **kwargs):
        """Lấy trạng thái hiện tại của agent"""
        try:
            asterisk_user = request.env['asterisk.user'].search([
                ('user_id', '=', request.env.uid),
                ('active', '=', True),
            ], limit=1)
            
            if not asterisk_user:
                return {'success': False, 'error': 'No asterisk user configured'}
            
            return {
                'success': True,
                'status': asterisk_user.status,
                'status_change_time': asterisk_user.status_change_time.isoformat() if asterisk_user.status_change_time else None,
            }
            
        except Exception as e:
            _logger.error('Error getting agent status: %s', str(e))
            return {'success': False, 'error': str(e)}
