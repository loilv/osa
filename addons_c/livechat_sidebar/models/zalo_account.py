import base64 as b64
import json
import logging
import re

import requests as req

from odoo import api, fields, models
from odoo.tools import html2plaintext

# Zalo reaction icon → Unicode emoji mapping
ZALO_REACTION_TO_EMOJI = {
    '/-heart': '❤️',
    '/-strong': '👍',
    ':>': '😆',
    ':o': '😮',
    ':-((' : '😢',
    ':-h': '😠',
    ':-*': '😘',
    ":')": '😂',
    '/-weak': '👎',
    '/-rose': '🌹',
    '/-break': '💔',
}
# Reverse: Odoo emoji → Zalo reaction icon
EMOJI_TO_ZALO_REACTION = {v: k for k, v in ZALO_REACTION_TO_EMOJI.items()}

_logger = logging.getLogger(__name__)


class ZaloAccount(models.Model):
    _name = 'zalo.account'
    _description = 'Tài khoản Zalo'
    _order = 'id desc'

    name = fields.Char(string='Tên tài khoản', required=True)
    bridge_url = fields.Char(
        string='Địa chỉ Bridge Server',
        required=True,
        default='http://localhost:3000',
    )
    account_id = fields.Char(
        string='Mã tài khoản Bridge',
        required=True,
        help='ID tài khoản trên bridge server (ví dụ: sale_team)',
    )
    zalo_id = fields.Char(string='Zalo UID', readonly=True)
    state = fields.Selection([
        ('disconnected', 'Ngắt kết nối'),
        ('connecting', 'Đang kết nối'),
        ('connected', 'Đã kết nối'),
        ('error', 'Lỗi'),
    ], string='Trạng thái', default='disconnected', readonly=True)
    user_ids = fields.Many2many(
        'res.users',
        'zalo_account_user_rel',
        'account_id',
        'user_id',
        string='Người dùng được phép',
        help='Các nhân viên Odoo được phép sử dụng tài khoản Zalo này. '
             'Để trống = tất cả đều dùng được.',
    )
    active = fields.Boolean(string='Kích hoạt', default=True)
    error_message = fields.Text(string='Thông tin lỗi', readonly=True)

    # ------------------------------------------------------------------
    # Bridge HTTP helpers
    # ------------------------------------------------------------------
    def _call_bridge(self, path, method='GET', data=None):
        """Call the zca-js bridge server."""
        self.ensure_one()
        url = '%s/api/accounts/%s/%s' % (
            self.bridge_url.rstrip('/'),
            self.account_id,
            path,
        )
        try:
            resp = req.request(method, url, json=data, timeout=30)
            return resp.json()
        except Exception as e:
            _logger.error('Bridge call failed: %s %s → %s', method, url, e)
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # Actions (buttons on form view)
    # ------------------------------------------------------------------
    def action_login(self):
        """Trigger login on the bridge server and open QR page."""
        self.ensure_one()
        url = '%s/api/accounts' % self.bridge_url.rstrip('/')
        try:
            req.post(url, json={
                'id': self.account_id,
                'force': True,
            }, timeout=30)
            self.write({'state': 'connecting', 'error_message': False})
        except Exception as e:
            self.write({'state': 'error', 'error_message': str(e)})
            return
        return {
            'type': 'ir.actions.act_url',
            'url': '%s/api/accounts/%s/qr' % (
                self.bridge_url.rstrip('/'),
                self.account_id,
            ),
            'target': 'new',
        }

    def action_check_status(self):
        """Check login status on bridge."""
        self.ensure_one()
        result = self._call_bridge('status')
        if result.get('loggedIn'):
            self.write({
                'state': 'connected',
                'zalo_id': result.get('zaloId', ''),
                'error_message': False,
            })
        elif result.get('loginState') == 'error':
            self.write({
                'state': 'error',
                'error_message': result.get('loginError', 'Unknown error'),
            })
        elif result.get('loginState') == 'logging_in':
            self.write({'state': 'connecting'})
        else:
            self.write({'state': 'disconnected'})

    def action_logout(self):
        """Logout from bridge."""
        self.ensure_one()
        url = '%s/api/accounts/%s' % (
            self.bridge_url.rstrip('/'),
            self.account_id,
        )
        try:
            req.delete(url, timeout=30)
        except Exception:
            pass
        self.write({'state': 'disconnected', 'zalo_id': False})


class MailMessage(models.Model):
    _inherit = 'mail.message'

    zalo_msg_id = fields.Char('Zalo Message ID', index=True)
    zalo_msg_data = fields.Text(
        'Zalo Message Data (JSON)',
        help='Full Zalo message data for quote/reaction features',
    )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    zalo_uid = fields.Char(string='Mã Zalo UID', index=True)


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    zalo_thread_id = fields.Char(string='Mã hội thoại Zalo')
    zalo_thread_type = fields.Selection([
        ('user', 'Người dùng'),
        ('group', 'Nhóm'),
    ], string='Loại hội thoại Zalo', default='user')
    zalo_account_id = fields.Many2one('zalo.account', string='Tài khoản Zalo')

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        # Skip if this message came from the Zalo webhook (avoid loop)
        if self.env.context.get('from_zalo_webhook'):
            return message
        # Forward agent messages to Zalo (only regular comments, not notifications)
        if (self.channel_type == 'livechat'
                and self.zalo_thread_id
                and self.zalo_account_id
                and self.zalo_account_id.state == 'connected'
                and message.author_id
                and message.message_type == 'comment'):
            visitor = self._get_zalo_visitor_partner()
            if visitor and message.author_id != visitor:
                self._forward_to_zalo(message)
        return message

    def _get_zalo_visitor_partner(self):
        for member in self.channel_member_ids:
            if member.livechat_member_type == 'visitor':
                return member.partner_id
        return self.env['res.partner']

    # Error codes / keywords returned by zca-js bridge when recipient blocks strangers
    _ZALO_BLOCK_STRANGER_INDICATORS = (
        'block_stranger',
        'stranger',
        'blocked',
        'not friend',
        'not_friend',
        '-501',
        '501',
        '122',
        'cannot send',
        'người lạ',
        'chặn',
    )

    def _is_zalo_block_stranger_error(self, result):
        """Return True if bridge result indicates the recipient blocks strangers."""
        if result.get('success'):
            return False
        err = str(result.get('error', '')).lower()
        code = str(result.get('errorCode', result.get('error_code', ''))).lower()
        combined = err + ' ' + code
        return any(kw in combined for kw in self._ZALO_BLOCK_STRANGER_INDICATORS)

    def _forward_to_zalo(self, message):
        try:
            text = html2plaintext(message.body or '').strip()
            attachments = []
            for att in message.attachment_ids:
                raw = att.raw
                if not raw:
                    continue
                attachments.append({
                    'fileName': att.name or 'file.dat',
                    'base64': b64.b64encode(raw).decode('ascii'),
                })
            # Build quote for reply (if replying to a Zalo message)
            quote = None
            if message.parent_id and message.parent_id.zalo_msg_data:
                try:
                    quote = json.loads(message.parent_id.zalo_msg_data)
                except (json.JSONDecodeError, TypeError):
                    pass

            payload = {
                'threadId': self.zalo_thread_id,
                'threadType': self.zalo_thread_type or 'user',
                'msg': text or '',
            }
            if attachments:
                payload['attachments'] = attachments
            if quote:
                payload['quote'] = quote

            if attachments or text:
                result = self.zalo_account_id._call_bridge(
                    'send-message',
                    method='POST',
                    data=payload,
                )
                _logger.info(
                    'Forwarded to Zalo thread %s: text=%s atts=%d quote=%s result=%s',
                    self.zalo_thread_id, text[:50] if text else '',
                    len(attachments), bool(quote), result,
                )
                if self._is_zalo_block_stranger_error(result):
                    _logger.warning(
                        'Zalo thread %s: recipient blocks strangers', self.zalo_thread_id,
                    )
                    self.with_context(from_zalo_webhook=True).message_post(
                        body='⚠️ Không thể gửi tin nhắn Zalo: người dùng này đang chặn tin nhắn từ người lạ',
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
        except Exception as e:
            _logger.error('Failed to forward to Zalo: %s', e)
