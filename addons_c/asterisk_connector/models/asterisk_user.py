# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AsteriskUser(models.Model):
    _name = 'asterisk.user'
    _description = 'Asterisk User Extension'
    _rec_name = 'display_name'

    user_id = fields.Many2one('res.users', string='Người dùng Odoo', required=True,
                              ondelete='cascade')
    server_id = fields.Many2one('asterisk.server', string='Server', required=True,
                                ondelete='cascade')
    extension = fields.Char(string='Extension/Số nội bộ', required=True)
    sip_password = fields.Char(string='SIP Password',
                               help='Mật khẩu SIP để đăng ký softphone với Asterisk')
    channel_type = fields.Selection([
        ('SIP', 'SIP'),
        ('PJSIP', 'PJSIP'),
        ('IAX2', 'IAX2'),
        ('DAHDI', 'DAHDI'),
    ], string='Loại Channel', default='PJSIP', required=True)

    call_type = fields.Selection([
        ('softphone', 'Softphone (WebRTC)'),
        ('ipphone', 'IP Phone'),
        ('both', 'Cả hai'),
    ], string='Loại thiết bị gọi', default='both', required=True,
        help='Softphone: Gọi qua trình duyệt web\nIP Phone: Gọi qua điện thoại IP\nCả hai: Có thể chọn khi gọi')

    caller_id = fields.Char(string='Caller ID')
    active = fields.Boolean(string='Active', default=True)

    display_name = fields.Char(string='Tên hiển thị', compute='_compute_display_name',
                               store=True)
    channel = fields.Char(string='Channel', compute='_compute_channel')

    call_log_ids = fields.One2many('asterisk.call.log', 'asterisk_user_id',
                                   string='Lịch sử cuộc gọi')

    status = fields.Selection([
        ('ready', 'Sẵn sàng'),
        ('personal_work', 'Làm việc riêng'),
        ('zalo_chat', 'Chat Zalo'),
        ('create_order', 'Tạo đơn'),
        ('check_order', 'Check đơn'),
        ('training', 'Học Đào tạo'),
        ('team_meeting', 'Họp nhóm'),
        ('offline', 'Offline'),
    ], string='Trạng thái',
        default='offline',
        required=True,
        help='Trạng thái làm việc của agent')
    status_change_time = fields.Datetime(string='Thời gian đổi trạng thái',
                                         default=fields.Datetime.now)

    _sql_constraints = [
        ('user_server_uniq', 'unique(user_id, server_id)',
         'Mỗi user chỉ có 1 extension trên mỗi server!'),
        ('extension_server_uniq', 'unique(extension, server_id)',
         'Extension phải duy nhất trên mỗi server!'),
    ]

    @api.depends('user_id', 'extension')
    def _compute_display_name(self):
        for rec in self:
            if rec.user_id and rec.extension:
                rec.display_name = f"{rec.user_id.name} ({rec.extension})"
            else:
                rec.display_name = rec.extension or ''

    @api.depends('channel_type', 'extension')
    def _compute_channel(self):
        for rec in self:
            if rec.channel_type and rec.extension:
                rec.channel = f"{rec.channel_type}/{rec.extension}"
            else:
                rec.channel = ''

    def make_call(self, phone_number):
        """Thực hiện cuộc gọi ra - chỉ cho phép khi online"""
        self.ensure_one()
        if not self.server_id:
            raise ValidationError(_('Chưa cấu hình server Asterisk'))

        # Kiểm tra trạng thái - chỉ ready mới được gọi
        if self.status != 'ready':
            raise ValidationError(_('Bạn phải ở trạng thái Sẵn sàng mới có thể gọi ra. Trạng thái hiện tại: %s') % dict(
                self._fields['status'].selection).get(self.status, self.status))

        # Làm sạch số điện thoại
        clean_number = ''.join(filter(str.isdigit, phone_number))

        # Log cuộc gọi
        call_log = self.env['asterisk.call.log'].create({
            'asterisk_user_id': self.id,
            'direction': 'outgoing',
            'phone_number': clean_number,
            'state': 'dialing',
        })

        # Originate call
        result = self.server_id.originate_call(
            channel=self.channel,
            exten=clean_number,
            caller_id=self.caller_id or self.extension,
        )

        _logger.info('Originate call result: %s', result)

        return {
            'call_log_id': call_log.id,
            'result': result,
        }

    def transfer_call(self, channel, target_extension):
        """Chuyển cuộc gọi đến extension khác"""
        self.ensure_one()
        if not self.server_id:
            raise ValidationError(_('Chưa cấu hình server Asterisk'))

        return self.server_id.transfer_call(channel, target_extension)

    def hangup(self, channel):
        """Kết thúc cuộc gọi"""
        self.ensure_one()
        if not self.server_id:
            raise ValidationError(_('Chưa cấu hình server Asterisk'))

        return self.server_id.hangup_call(channel)

    def hold_call(self, channel, hold=True):
        """Hold/Unhold cuộc gọi"""
        self.ensure_one()
        if not self.server_id:
            raise ValidationError(_('Chưa cấu hình server Asterisk'))

        if hold:
            return self.server_id.hold_call(channel)
        else:
            return self.server_id.unhold_call(channel)

    def mute_call(self, channel, mute=True):
        """Mute/Unmute cuộc gọi"""
        self.ensure_one()
        if not self.server_id:
            raise ValidationError(_('Chưa cấu hình server Asterisk'))

        if mute:
            return self.server_id.mute_call(channel)
        else:
            return self.server_id.unmute_call(channel)

    @api.model
    def get_current_user_asterisk(self):
        """Lấy cấu hình Asterisk của user hiện tại"""
        asterisk_user = self.search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ], limit=1)

        if asterisk_user:
            server = asterisk_user.server_id
            # Build WebSocket URL
            ws_protocol = 'wss' if server.use_ssl else 'ws'
            ws_url = f"{ws_protocol}://{server.host}:{server.ws_port}{server.ws_path}"

            return {
                'id': asterisk_user.id,
                'extension': asterisk_user.extension,
                'sip_password': asterisk_user.sip_password,
                'channel': asterisk_user.channel,
                'channel_type': asterisk_user.channel_type,
                'server_id': server.id,
                'server_host': server.host,
                'caller_id': asterisk_user.caller_id,
                'call_type': asterisk_user.call_type,
                # WebRTC config
                'ws_enabled': server.ws_enabled,
                'ws_url': ws_url,
                'sip_domain': server.host,
                'status': asterisk_user.status,
                'status_change_time': asterisk_user.status_change_time.isoformat() if asterisk_user.status_change_time else None,
            }
        return {}

    def update_status(self, new_status, reason=None):
        """Cập nhật trạng thái và tạo log"""
        self.ensure_one()

        old_status = self.status
        if old_status == new_status:
            return {'success': True, 'message': 'Status unchanged'}

        # Tính duration ở trạng thái cũ
        duration = 0
        if self.status_change_time:
            delta = datetime.now() - self.status_change_time
            duration = delta.total_seconds() / 60  # minutes

        # Tạo log
        self.env['asterisk.user.status.log'].sudo().create({
            'asterisk_user_id': self.id,
            'old_status': old_status,
            'new_status': new_status,
            'duration': duration,
            'reason': reason,
        })

        # Cập nhật trạng thái mới
        self.write({
            'status': new_status,
            'status_change_time': fields.Datetime.now(),
        })

        # Cập nhật trạng thái trên Asterisk AMI
        ami_error = None
        if self.server_id:
            try:
                if new_status == 'ready':
                    # Unpause để nhận cuộc gọi
                    self.server_id.set_extension_pause(self.extension, enable=False)
                    self.server_id.set_extension_dnd(self.extension, enable=False)
                elif new_status == 'offline':
                    # DND + Pause
                    self.server_id.set_extension_dnd(self.extension, enable=True)
                    self.server_id.set_extension_pause(self.extension, enable=True, reason=new_status)
                else:
                    # Pause trong queue với reason (personal_work, zalo_chat, create_order, check_order, training, team_meeting)
                    self.server_id.set_extension_pause(self.extension, enable=True, reason=new_status)
            except Exception as e:
                _logger.warning("AMI update failed for extension %s: %s", self.extension, e)
                ami_error = str(e)

        result = {
            'success': True,
            'old_status': old_status,
            'new_status': new_status,
            'duration': duration,
        }
        if ami_error:
            result['ami_warning'] = ami_error
        return result

    @api.model
    def update_status_for_current_user(self, new_status, reason=None):
        """Cập nhật trạng thái cho user hiện tại - gọi từ frontend"""
        asterisk_user = self.search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ], limit=1)

        if not asterisk_user:
            return {'success': False, 'error': 'No asterisk user configured'}

        return asterisk_user.update_status(new_status, reason)

    @api.model
    def get_current_user_status(self):
        """Lấy trạng thái hiện tại của user - gọi từ frontend"""
        asterisk_user = self.search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ], limit=1)

        if not asterisk_user:
            return {'success': False, 'error': 'No asterisk user configured'}

        return {
            'success': True,
            'status': asterisk_user.status,
            'status_change_time': asterisk_user.status_change_time.isoformat() if asterisk_user.status_change_time else None,
        }

    def can_make_call(self):
        """Kiểm tra có thể gọi ra không - chỉ ready mới được gọi"""
        self.ensure_one()
        return self.status == 'ready'

    def can_receive_call(self):
        """Kiểm tra có thể nhận cuộc gọi không - chỉ ready mới được nhận"""
        self.ensure_one()
        return self.status == 'ready'
