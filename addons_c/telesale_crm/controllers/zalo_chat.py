import logging

from odoo import http, Command
from odoo.http import request

_logger = logging.getLogger(__name__)


class TelesaleCrmZaloController(http.Controller):

    def _get_zalo_account(self):
        """Get the active Zalo account linked to the current user."""
        ZaloAccount = request.env.get('zalo.account')
        if ZaloAccount is None:
            return None
        account = ZaloAccount.sudo().search([
            ('user_ids', 'in', [request.env.user.id]),
            ('state', '=', 'connected'),
        ], limit=1)
        if not account:
            account = ZaloAccount.sudo().search([
                ('user_ids', '=', False),
                ('state', '=', 'connected'),
            ], limit=1)
        if not account:
            account = ZaloAccount.sudo().search([
                ('state', '=', 'connected'),
            ], limit=1)
        return account

    @http.route('/telesale_crm/zalo_lookup', type='json', auth='user')
    def zalo_lookup(self, phone=None):
        """Look up Zalo user info by phone (without auto-sending friend request)."""
        if not phone or not phone.strip():
            return {'success': False, 'error': 'Số điện thoại không được để trống.'}
        phone = phone.strip()
        account = self._get_zalo_account()
        if not account:
            return {'success': False, 'error': 'Không tìm thấy tài khoản Zalo đã kết nối.'}
        try:
            result = account._call_bridge(
                'find-user', method='POST', data={'phone': phone},
            )
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'Không tìm thấy người dùng Zalo.')}
            user_data = result.get('data', {})
            uid = user_data.get('uid', '')
            # Check if friend
            is_friend = False
            friends_result = account._call_bridge('friends', method='GET')
            if friends_result.get('success'):
                friend_ids = {
                    str(f.get('userId', ''))
                    for f in (friends_result.get('data') or [])
                }
                is_friend = str(uid) in friend_ids
            return {
                'success': True,
                'data': {
                    'zalo_id': uid,
                    'display_name': (
                        user_data.get('display_name', '')
                        or user_data.get('zalo_name', '')
                    ),
                    'avatar': user_data.get('avatar', ''),
                    'phone': phone,
                    'is_friend': is_friend,
                },
            }
        except Exception as e:
            _logger.error('Zalo lookup failed for %s: %s', phone, str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/telesale_crm/zalo_send_friend_request', type='json', auth='user')
    def zalo_send_friend_request(self, phone=None, message=None):
        """Send a Zalo friend request with custom message."""
        if not phone or not phone.strip():
            return {'success': False, 'error': 'Số điện thoại không được để trống.'}
        phone = phone.strip()
        msg = (message or '').strip() or 'Xin chào! Tôi muốn kết bạn với bạn.'
        account = self._get_zalo_account()
        if not account:
            return {'success': False, 'error': 'Không tìm thấy tài khoản Zalo đã kết nối.'}
        try:
            find_result = account._call_bridge(
                'find-user', method='POST', data={'phone': phone},
            )
            if not find_result.get('success'):
                return {'success': False, 'error': 'Không tìm thấy người dùng Zalo với số điện thoại này.'}
            uid = find_result.get('data', {}).get('uid', '')
            if not uid:
                return {'success': False, 'error': 'Không tìm thấy Zalo ID.'}
            result = account._call_bridge(
                'send-friend-request',
                method='POST',
                data={'userId': uid, 'msg': msg},
            )
            if result.get('success'):
                _logger.info('Zalo friend request sent to %s (uid: %s) msg: %s', phone, uid, msg[:50])
                return {'success': True, 'message': 'Đã gửi lời mời kết bạn thành công!'}
            return {'success': False, 'error': result.get('error', 'Gửi lời mời thất bại.')}
        except Exception as e:
            _logger.error('Zalo friend request failed for %s: %s', phone, str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/telesale_crm/zalo_open_chat', type='json', auth='user')
    def zalo_open_chat(self, phone=None, lead_name=None):
        """Create or find a discuss channel for this phone and return channel_id."""
        if not phone or not phone.strip():
            return {'success': False, 'error': 'Số điện thoại không được để trống.'}
        phone = phone.strip()
        try:
            # Find or create partner by phone
            partner = request.env['res.partner'].sudo().search([('phone', '=', phone)], limit=1)
            partner_name = (lead_name or '').strip() or phone
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': partner_name,
                    'phone': phone,
                })
            operator = request.env.user.partner_id
            # Check for existing open session
            existing_channel = request.env['discuss.channel'].sudo().search([
                ('channel_type', '=', 'livechat'),
                ('channel_member_ids.partner_id', '=', partner.id),
                ('livechat_end_dt', '=', False),
            ], order='create_date desc', limit=1)
            if existing_channel:
                return {'success': True, 'channel_id': existing_channel.id}
            # Find livechat channel
            livechat_channel = request.env['im_livechat.channel'].sudo().search([
                ('user_ids', 'in', [request.env.user.id]),
            ], limit=1)
            if not livechat_channel:
                livechat_channel = request.env['im_livechat.channel'].sudo().search([], limit=1)
            if not livechat_channel:
                return {'success': False, 'error': 'Chưa cấu hình kênh livechat.'}
            # Create channel
            channel = request.env['discuss.channel'].sudo().create({
                'channel_member_ids': [
                    Command.create({
                        'partner_id': operator.id,
                        'livechat_member_type': 'agent',
                    }),
                    Command.create({
                        'partner_id': partner.id,
                        'livechat_member_type': 'visitor',
                    }),
                ],
                'livechat_operator_id': operator.id,
                'livechat_channel_id': livechat_channel.id,
                'livechat_status': 'in_progress',
                'channel_type': 'livechat',
                'name': partner.name or phone,
            })
            channel._broadcast([operator.id])
            # Try to link Zalo thread
            account = self._get_zalo_account()
            if account:
                try:
                    find_result = account._call_bridge(
                        'find-user', method='POST', data={'phone': phone},
                    )
                    if find_result.get('success'):
                        uid = find_result.get('data', {}).get('uid', '')
                        if uid:
                            partner.sudo().write({'zalo_uid': uid})
                            channel.sudo().write({
                                'zalo_thread_id': uid,
                                'zalo_account_id': account.id,
                            })
                except Exception as e:
                    _logger.warning('Could not link Zalo for %s: %s', phone, e)
            return {'success': True, 'channel_id': channel.id}
        except Exception as e:
            _logger.error('Error creating Zalo chat session for %s: %s', phone, str(e))
            return {'success': False, 'error': str(e)}
