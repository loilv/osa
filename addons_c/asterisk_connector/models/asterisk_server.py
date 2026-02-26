# -*- coding: utf-8 -*-

import logging
from asterisk.ami import AMIClient, SimpleAction
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AsteriskServer(models.Model):
    _name = 'asterisk.server'
    _description = 'Asterisk Server Configuration'

    name = fields.Char(string='Tên Server', required=True)
    host = fields.Char(string='Host/IP', required=True, default='localhost')
    ami_port = fields.Integer(string='AMI Port', default=5038)
    ami_username = fields.Char(string='AMI Username', required=True)
    ami_password = fields.Char(string='AMI Password', required=True)
    ari_port = fields.Integer(string='ARI Port', default=8088)
    ari_username = fields.Char(string='ARI Username')
    ari_password = fields.Char(string='ARI Password')
    use_ssl = fields.Boolean(string='Sử dụng SSL', default=False)
    
    # WebRTC/WebSocket configuration
    ws_enabled = fields.Boolean(string='Bật WebRTC', default=True, 
                                help='Cho phép softphone đăng ký SIP qua WebSocket')
    ws_port = fields.Integer(string='WebSocket Port', default=8089,
                             help='Port WebSocket của Asterisk (thường là 8089 cho wss hoặc 8088 cho ws)')
    ws_path = fields.Char(string='WebSocket Path', default='/ws',
                          help='Đường dẫn WebSocket, ví dụ: /ws')
    recording_base_url = fields.Char(
        string='Recording Base URL',
        help='Base URL để truy cập file ghi âm, ví dụ: https://domain.com/recordings')
    active = fields.Boolean(string='Active', default=True)
    state = fields.Selection([
        ('disconnected', 'Chưa kết nối'),
        ('connected', 'Đã kết nối'),
        ('error', 'Lỗi'),
    ], string='Trạng thái', default='disconnected', readonly=True)
    last_connection = fields.Datetime(string='Lần kết nối cuối', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', 
                                  default=lambda self: self.env.company)
    user_ids = fields.One2many('asterisk.user', 'server_id', string='Users')
    
    context_outgoing = fields.Char(string='Context gọi ra', default='from-internal')
    context_incoming = fields.Char(string='Context gọi vào', default='from-external')
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Tên server phải duy nhất trong công ty!')
    ]

    def _get_ami_client(self):
        """Tạo và login AMI client, trả về client đã đăng nhập"""
        self.ensure_one()
        try:
            client = AMIClient(address=self.host, port=self.ami_port)
            client.login(username=self.ami_username, secret=self.ami_password)
            return client
        except Exception as e:
            _logger.error('AMI connection error: %s', str(e))
            raise UserError(_('Lỗi kết nối AMI tới %s:%s - %s') % (self.host, self.ami_port, str(e)))

    def action_test_connection(self):
        """Test kết nối tới Asterisk AMI"""
        self.ensure_one()
        client = None
        try:
            client = self._get_ami_client()
            
            # Gửi Ping action để kiểm tra kết nối
            action = SimpleAction('Ping')
            future = client.send_action(action)
            response = future.response
            
            if response and response.status == 'Success':
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Thành công'),
                        'message': _('Kết nối tới Asterisk thành công!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.state = 'error'
                raise UserError(_('Đăng nhập AMI thất bại. Kiểm tra username/password.'))
                
        except UserError:
            raise
        except Exception as e:
            self.state = 'error'
            raise UserError(_('Lỗi kết nối: %s') % str(e))
        finally:
            if client:
                try:
                    client.logoff()
                except Exception:
                    pass

    def _ami_send_action(self, action_dict):
        """Gửi action tới AMI và nhận response"""
        self.ensure_one()
        client = None
        try:
            client = self._get_ami_client()
            
            # Tách Action name ra khỏi dict, các key còn lại là params
            action_name = action_dict.pop('Action')
            action = SimpleAction(action_name, **action_dict)
            
            future = client.send_action(action)
            response = future.response
            
            _logger.info('AMI Action %s response: %s', action_name, response)
            return response
            
        except UserError:
            raise
        except Exception as e:
            _logger.error('AMI Error: %s', str(e))
            raise UserError(_('AMI Error: %s') % str(e))
        finally:
            if client:
                try:
                    client.logoff()
                except Exception:
                    pass

    def originate_call(self, channel, exten, caller_id=None, context=None):
        """Khởi tạo cuộc gọi từ AMI"""
        self.ensure_one()
        context = context or self.context_outgoing
        client = None
        
        _logger.info('AMI Originate: channel=%s, exten=%s, context=%s, caller_id=%s', 
                     channel, exten, context, caller_id)
        
        try:
            client = self._get_ami_client()
            
            kwargs = {
                'Channel': channel,
                'Context': context,
                'Exten': exten,
                'Priority': '1',
            }
            if caller_id:
                kwargs['CallerID'] = caller_id
            
            action = SimpleAction('Originate', **kwargs)
            future = client.send_action(action)
            response = future.response
            
            _logger.info('AMI Originate result: %s', response)
            return response
            
        except UserError:
            raise
        except Exception as e:
            _logger.error('AMI Originate error: %s', str(e))
            raise UserError(_('AMI Originate Error: %s') % str(e))
        finally:
            if client:
                try:
                    client.logoff()
                except Exception:
                    pass

    def transfer_call(self, channel, exten, context=None):
        """Chuyển cuộc gọi"""
        self.ensure_one()
        context = context or self.context_outgoing
        
        action = {
            'Action': 'Redirect',
            'Channel': channel,
            'Context': context,
            'Exten': exten,
            'Priority': '1',
        }
        return self._ami_send_action(dict(action))

    def hangup_call(self, channel):
        """Kết thúc cuộc gọi"""
        self.ensure_one()
        action = {
            'Action': 'Hangup',
            'Channel': channel,
        }
        return self._ami_send_action(dict(action))

    def get_active_channels(self):
        """Lấy danh sách channel đang hoạt động"""
        self.ensure_one()
        action = {
            'Action': 'CoreShowChannels',
        }
        return self._ami_send_action(dict(action))

    def hold_call(self, channel):
        """Đặt cuộc gọi ở chế độ hold"""
        self.ensure_one()
        action = {
            'Action': 'Hold',
            'Channel': channel,
        }
        return self._ami_send_action(dict(action))

    def unhold_call(self, channel):
        """Bỏ hold cuộc gọi"""
        self.ensure_one()
        action = {
            'Action': 'Hold',
            'Channel': channel,
            'Status': 'off',
        }
        return self._ami_send_action(dict(action))

    def mute_call(self, channel, direction='all'):
        """Tắt tiếng cuộc gọi
        direction: 'in', 'out', 'all'
        """
        self.ensure_one()
        action = {
            'Action': 'MuteAudio',
            'Channel': channel,
            'Direction': direction,
            'State': 'on',
        }
        return self._ami_send_action(dict(action))

    def unmute_call(self, channel, direction='all'):
        """Bật lại tiếng cuộc gọi"""
        self.ensure_one()
        action = {
            'Action': 'MuteAudio',
            'Channel': channel,
            'Direction': direction,
            'State': 'off',
        }
        return self._ami_send_action(dict(action))

    def get_extensions_from_ami(self):
        """Lấy danh sách extensions từ Asterisk AMI"""
        self.ensure_one()
        client = None
        try:
            client = self._get_ami_client()
            
            # Gửi lệnh lấy PJSIP endpoints
            action = SimpleAction('PJSIPShowEndpoints')
            future = client.send_action(action)
            response = future.response
            
            extensions = []
            if response:
                # Parse response keys để tìm endpoints
                response_str = str(response)
                for line in response_str.split('\r\n'):
                    if line.startswith('ObjectName: '):
                        ext = line.replace('ObjectName: ', '').strip()
                        ext_names = [e['extension'] for e in extensions]
                        if ext and ext not in ext_names:
                            extensions.append({
                                'extension': ext,
                                'server_id': self.id,
                                'server_name': self.name,
                            })
            
            return extensions
            
        except Exception as e:
            _logger.error('Error getting extensions from AMI: %s', str(e))
            return []
        finally:
            if client:
                try:
                    client.logoff()
                except Exception:
                    pass

    def set_extension_dnd(self, extension, enable=True):
        """Bật/tắt Do Not Disturb cho extension qua AMI - dùng DEVICE_STATE để chặn cuộc gọi"""
        self.ensure_one()
        client = None
        try:
            client = self._get_ami_client()
            
            # Dùng DEVICE_STATE để đặt trạng thái endpoint
            # Khi UNAVAILABLE: Asterisk sẽ không route cuộc gọi đến endpoint này
            device_state = 'UNAVAILABLE' if enable else 'NOT_INUSE'
            action = SimpleAction(
                'SetVar',
                Variable=f'DEVICE_STATE(PJSIP/{extension})',
                Value=device_state,
            )
            future = client.send_action(action)
            response = future.response
            
            return response and response.status == 'Success'
        except Exception as e:
            _logger.error('Error setting DND for %s: %s', extension, str(e))
            return False
        finally:
            if client:
                try:
                    client.logoff()
                except Exception:
                    pass

    def set_extension_pause(self, extension, queue_name=None, enable=True, reason=None):
        """Pause/Unpause extension trong queue qua AMI"""
        self.ensure_one()
        client = None
        try:
            client = self._get_ami_client()
            
            # QueuePause dùng cho cả pause và unpause
            kwargs = {
                'Interface': f'PJSIP/{extension}',
                'Paused': 'true' if enable else 'false',
            }
            if reason and enable:
                kwargs['Reason'] = reason
            
            action = SimpleAction('QueuePause', **kwargs)
            future = client.send_action(action)
            response = future.response
            
            return response and response.status == 'Success'
        except Exception as e:
            _logger.error('Error setting pause for %s: %s', extension, str(e))
            return False
        finally:
            if client:
                try:
                    client.logoff()
                except Exception:
                    pass
