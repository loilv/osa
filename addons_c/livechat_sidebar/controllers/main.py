import base64
import json
import logging
import mimetypes
import re

import pytz
import requests as http_req

from odoo import Command, http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class LivechatSidebarController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _to_user_tz(self, dt):
        if not dt:
            return ''
        return fields.Datetime.context_timestamp(
            request,
            dt
        ).isoformat()

    def _get_zalo_account(self):
        """Get the active Zalo account linked to the current user."""
        ZaloAccount = request.env.get('zalo.account')
        if ZaloAccount is None:
            return None
        # Tìm tài khoản Zalo mà user hiện tại được phép dùng
        account = ZaloAccount.sudo().search([
            ('user_ids', 'in', [request.env.user.id]),
            ('state', '=', 'connected'),
        ], limit=1)
        if not account:
            # Fallback: tài khoản không giới hạn user (user_ids trống)
            account = ZaloAccount.sudo().search([
                ('user_ids', '=', False),
                ('state', '=', 'connected'),
            ], limit=1)
        if not account:
            # Fallback cuối: bất kỳ tài khoản connected nào
            account = ZaloAccount.sudo().search([
                ('state', '=', 'connected'),
            ], limit=1)
        return account

    def _get_zalo_account_for_webhook(self, account_id_str):
        """Get zalo.account by bridge account_id string."""
        ZaloAccount = request.env.get('zalo.account')
        if ZaloAccount is None:
            return None
        return ZaloAccount.sudo().search([
            ('account_id', '=', account_id_str),
        ], limit=1)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    @http.route('/livechat_sidebar/create_session', type='json', auth='user')
    def create_session(self, phone=None):
        """Create a new livechat session for the given phone number."""
        if not phone or not phone.strip():
            return {'error': 'Phone number is required.'}
        phone = phone.strip()
        # Find or create partner by phone
        partner = request.env['res.partner'].sudo().search([('phone', '=', phone)], limit=1)
        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': phone,
                'phone': phone,
            })
        operator = request.env.user.partner_id
        # Find a livechat channel where the current user is an operator
        livechat_channel = request.env['im_livechat.channel'].sudo().search([
            ('user_ids', 'in', [request.env.user.id]),
        ], limit=1)
        if not livechat_channel:
            livechat_channel = request.env['im_livechat.channel'].sudo().search([], limit=1)
        if not livechat_channel:
            return {'error': 'No livechat channel configured.'}
        # Build channel name
        visitor_name = partner.name or phone
        operator_name = request.env.user.livechat_username or request.env.user.name
        channel_name = '%s %s' % (visitor_name, operator_name)
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
            'name': channel_name,
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
        return {'channel_id': channel.id}

    @http.route('/livechat_sidebar/get_sessions', type='json', auth='user')
    def get_sessions(self, current_channel_id=None, search_query=None):
        """Fetch livechat sessions assigned to the current agent."""
        partner = request.env.user.partner_id
        domain = [
            ('channel_type', '=', 'livechat'),
            ('livechat_operator_id', '=', partner.id),
        ]
        if search_query:
            domain.append(('name', 'ilike', search_query))
        channels = request.env['discuss.channel'].search(
            domain, order='create_date desc', limit=50,
        )
        sessions = []
        for ch in channels:
            last_message = request.env['mail.message'].search([
                ('model', '=', 'discuss.channel'),
                ('res_id', '=', ch.id),
                ('message_type', '!=', 'notification'),
            ], order='id desc', limit=1)
            agent_replied = False
            if last_message and last_message.author_id == partner:
                agent_replied = True
            elif not last_message:
                agent_replied = False
            else:
                agent_messages = request.env['mail.message'].search([
                    ('model', '=', 'discuss.channel'),
                    ('res_id', '=', ch.id),
                    ('message_type', '!=', 'notification'),
                    ('author_id', '=', partner.id),
                ], limit=1)
                if not agent_messages:
                    agent_replied = False
                else:
                    agent_replied = last_message.author_id == partner
            visitor_name = ''
            visitor_phone = ''
            for hist in ch.livechat_customer_history_ids:
                if hist.partner_id:
                    visitor_name = hist.partner_id.name
                    visitor_phone = hist.partner_id.phone or ''
                elif hist.guest_id:
                    visitor_name = hist.guest_id.name
                if visitor_name:
                    break
            if not visitor_phone:
                phone_match = re.search(r'\d{9,15}', ch.name or '')
                if phone_match:
                    visitor_phone = phone_match.group(0)
            sessions.append({
                'id': ch.id,
                'name': ch.name or '',
                'visitor_name': ch.name or visitor_name or 'Visitor',
                'visitor_phone': visitor_phone,
                'create_date': self._to_user_tz(ch.create_date) if ch.create_date else '',
                'livechat_end_dt': self._to_user_tz(ch.livechat_end_dt) if ch.livechat_end_dt else '',
                'livechat_status': ch.livechat_status or '',
                'is_closed': bool(ch.livechat_end_dt),
                'last_message_body': last_message.preview if last_message else '',
                'last_message_date': self._to_user_tz(last_message.date) if last_message and last_message.date else '',
                'is_active': ch.id == current_channel_id,
                'country_code': ch.country_id.code.lower() if ch.country_id and ch.country_id.code else '',
                'agent_replied': agent_replied,
                'zalo_linked': bool(ch.zalo_thread_id),
            })
        sessions.sort(key=lambda s: (
            s['is_closed'],
            s['agent_replied'],
            not bool(s['last_message_date']),
        ))
        return sessions

    # ------------------------------------------------------------------
    # Zalo API (gọi qua bridge server)
    # ------------------------------------------------------------------
    @http.route('/livechat_sidebar/zalo_get_user_info', type='json', auth='user')
    def zalo_get_user_info(self, phone=None):
        """Look up Zalo user info by phone number via bridge server."""
        if not phone or not phone.strip():
            return {'success': False, 'error': 'Phone number is required.'}
        phone = phone.strip()
        account = self._get_zalo_account()
        if not account:
            return {'success': False, 'error': 'No connected Zalo account found.'}
        try:
            # Find user by phone
            result = account._call_bridge(
                'find-user', method='POST', data={'phone': phone},
            )
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'User not found on Zalo.')}
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
            _logger.error('Failed to get Zalo user info for %s: %s', phone, str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/livechat_sidebar/zalo_send_friend_request', type='json', auth='user')
    def zalo_send_friend_request(self, phone=None, channel_id=None):
        """Send a Zalo friend request via bridge server."""
        if not phone or not phone.strip():
            return {'success': False, 'error': 'Phone number is required.'}
        phone = phone.strip()
        account = self._get_zalo_account()
        if not account:
            return {'success': False, 'error': 'No connected Zalo account found.'}
        try:
            # First find user to get userId
            find_result = account._call_bridge(
                'find-user', method='POST', data={'phone': phone},
            )
            if not find_result.get('success'):
                return {'success': False, 'error': 'Cannot find Zalo user with this phone.'}
            uid = find_result.get('data', {}).get('uid', '')
            if not uid:
                return {'success': False, 'error': 'Zalo user ID not found.'}
            # Send friend request
            result = account._call_bridge(
                'send-friend-request',
                method='POST',
                data={
                    'userId': uid,
                    'msg': 'Xin chào! Tôi muốn kết bạn với bạn.',
                },
            )
            if result.get('success'):
                _logger.info('Zalo friend request sent to %s (uid: %s)', phone, uid)
                return {'success': True, 'message': 'Friend request sent successfully.'}
            return {'success': False, 'error': result.get('error', 'Failed to send friend request.')}
        except Exception as e:
            _logger.error('Failed to send Zalo friend request to %s: %s', phone, str(e))
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Webhook — nhận tin nhắn realtime từ bridge server
    # ------------------------------------------------------------------
    @http.route('/zalo/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def zalo_webhook(self, **kw):
        """Receive Zalo events from the zca-js bridge server.

        Bridge gửi JSON-RPC: {"jsonrpc":"2.0","params":{event, threadId, ...}}
        Odoo tự unpack params vào **kw.
        """
        data = kw
        event = data.get('event')
        _logger.info('[Zalo Webhook] event=%s accountId=%s', event, data.get('accountId'))
        try:
            if event == 'new_message':
                self._handle_zalo_message(data)
            elif event == 'reaction':
                self._handle_zalo_reaction(data)
            elif event == 'friend_event':
                _logger.info('[Zalo Webhook] Friend event: %s', data)
        except Exception as e:
            _logger.error('[Zalo Webhook] Error handling event: %s', e, exc_info=True)
        return {'status': 'ok'}

    # ------------------------------------------------------------------
    # Zalo content parser — download files & return for message_post
    # ------------------------------------------------------------------
    def _download_zalo_file(self, url):
        """Download a file from *url*.

        Returns tuple ``(filename, bytes, content_type)`` or ``None``.
        """
        if not url:
            return None
        try:
            resp = http_req.get(url, timeout=30)
            if resp.status_code != 200:
                _logger.warning('[Zalo] Download failed %s → HTTP %s', url, resp.status_code)
                return None
            data = resp.content
            if not data:
                return None
            ct = resp.headers.get('Content-Type', 'application/octet-stream').split(';')[0].strip()
            _logger.info('[Zalo] Downloaded %d bytes (%s) from %s', len(data), ct, url[:120])
            return data, ct
        except Exception as e:
            _logger.error('[Zalo] Failed to download %s: %s', url, e)
            return None

    def _parse_zalo_content(self, msg_data):
        """Parse Zalo msg_data.content.

        Returns ``{'body': str, 'attachments': list[tuple(name, bytes)]}``.
        ``attachments`` items are ``(filename, raw_bytes)`` ready for
        ``message_post(attachments=...)``.
        """
        content = msg_data.get('content', '')
        msg_type = msg_data.get('msgType', '')

        # Plain text
        if isinstance(content, str):
            if not content.strip():
                return {'body': '', 'attachments': []}
            return {'body': content, 'attachments': []}

        # Object — attachment / image / file / link / sticker
        if isinstance(content, dict):
            _logger.info(
                '[Zalo] Parsing content: msgType=%s keys=%s',
                msg_type, list(content.keys()),
            )

            # Sticker (msgType=chat.sticker or content has id+cateId)
            sticker_id = content.get('id')
            if msg_type == 'chat.sticker' or (sticker_id and content.get('cateId') is not None):
                sticker_url = (
                    'https://zalo-api.zadn.vn/api/emoticon/sticker/webpc'
                    '?eid=%s&size=130' % sticker_id
                )
                result = self._download_zalo_file(sticker_url)
                if result:
                    return {'body': '', 'attachments': [('sticker_%s.png' % sticker_id, result[0])]}
                return {'body': '[Sticker]', 'attachments': []}

            href = content.get('href', '')
            thumb = content.get('thumb', '')
            title = content.get('title', '')
            description = content.get('description', '')

            # Detect image via thumb / normalUrl / hdUrl / href extension
            normal_url = content.get('normalUrl', '') or content.get('hdUrl', '')
            is_image = bool(thumb or normal_url)
            if not is_image and href:
                is_image = any(href.lower().endswith(ext) for ext in
                               ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))

            if is_image:
                img_url = normal_url or href or thumb
                fname = title or 'zalo_image.jpg'
                if '.' not in fname:
                    fname += '.jpg'
                result = self._download_zalo_file(img_url)
                if result:
                    return {'body': '', 'attachments': [(fname, result[0])]}
                return {'body': '[Ảnh từ Zalo]', 'attachments': []}

            # File / video
            if href:
                fname = title or 'zalo_file'
                if '.' not in fname:
                    fname += '.dat'
                result = self._download_zalo_file(href)
                if result:
                    file_bytes, ct = result
                    # Fix extension based on content-type if needed
                    if fname.endswith('.dat'):
                        ext = mimetypes.guess_extension(ct) or ''
                        if ext:
                            fname = fname.replace('.dat', ext)
                    return {'body': description or '', 'attachments': [(fname, file_bytes)]}
                return {'body': '[File từ Zalo: %s]' % fname, 'attachments': []}

            # Sticker or other without href
            if thumb:
                result = self._download_zalo_file(thumb)
                if result:
                    sname = (title or 'sticker') + '.png'
                    return {'body': '', 'attachments': [(sname, result[0])]}
            if title:
                return {'body': '[Sticker: %s]' % title, 'attachments': []}

            _logger.warning('[Zalo] Unknown content: msgType=%s keys=%s content=%s',
                            msg_type, list(content.keys()), str(content)[:200])
            return {'body': '[Tin nhắn Zalo không hỗ trợ]', 'attachments': []}

        _logger.warning('[Zalo] Unsupported content type: %s', type(content))
        return {'body': '[Tin nhắn không hỗ trợ]', 'attachments': []}

    def _handle_zalo_message(self, data):
        """Handle incoming Zalo message — create/find channel and post."""
        thread_id = data.get('threadId')
        account_id_str = data.get('accountId')
        msg_data = data.get('data', {})
        is_self = data.get('isSelf', False)
        zalo_type = data.get('type', 'user')  # "user" or "group"
        if is_self or not thread_id:
            return
        _logger.info('[Zalo Webhook] type=%s threadId=%s', zalo_type, thread_id)
        # Find account
        account = self._get_zalo_account_for_webhook(account_id_str)
        if not account:
            _logger.warning('[Zalo Webhook] Account %s not found', account_id_str)
            return
        # Determine sender: for groups, use uidFrom; for users, use threadId
        uid_from = str(msg_data.get('uidFrom', ''))
        if zalo_type == 'group' and uid_from:
            sender_zalo_uid = uid_from
        else:
            sender_zalo_uid = thread_id
        # Find or create partner for the sender
        partner = request.env['res.partner'].sudo().search([
            ('zalo_uid', '=', sender_zalo_uid),
        ], limit=1)
        if not partner:
            # Fetch user info from Zalo via bridge
            zalo_name = 'Zalo %s' % sender_zalo_uid
            zalo_avatar_b64 = False
            try:
                info_resp = account._call_bridge(
                    'get-user-info', method='POST',
                    data={'userId': sender_zalo_uid},
                )
                profiles = (info_resp.get('data') or {}).get('changed_profiles') or {}
                # Profile key is "uid_0" format
                profile = profiles.get('%s_0' % sender_zalo_uid) or {}
                if not profile:
                    # Try without suffix
                    profile = next(iter(profiles.values()), {})
                fetched_name = profile.get('displayName') or profile.get('zaloName') or ''
                if fetched_name:
                    zalo_name = fetched_name
                avatar_url = profile.get('avatar') or ''
                if avatar_url:
                    dl = self._download_zalo_file(avatar_url)
                    if dl:
                        zalo_avatar_b64 = base64.b64encode(dl[0]).decode('ascii')
                _logger.info(
                    '[Zalo Webhook] Fetched user info for %s: name=%s avatar=%s',
                    sender_zalo_uid, zalo_name, bool(zalo_avatar_b64),
                )
            except Exception as e:
                _logger.warning(
                    '[Zalo Webhook] Failed to fetch user info for %s: %s',
                    sender_zalo_uid, e,
                )
            partner_vals = {
                'name': zalo_name,
                'zalo_uid': sender_zalo_uid,
            }
            if zalo_avatar_b64:
                partner_vals['image_1920'] = zalo_avatar_b64
            partner = request.env['res.partner'].sudo().create(partner_vals)
        # Find existing channel (by thread_id = group ID or user ID)
        channel = request.env['discuss.channel'].sudo().search([
            ('channel_type', '=', 'livechat'),
            ('zalo_thread_id', '=', thread_id),
            ('zalo_account_id', '=', account.id),
        ], limit=1)
        if not channel:
            # Lấy operator đầu tiên từ danh sách user_ids
            first_user = account.user_ids[:1] if account.user_ids else None
            operator = (
                first_user.partner_id
                if first_user
                else request.env['res.users'].sudo().browse(2).partner_id
            )
            livechat_channel = request.env['im_livechat.channel'].sudo().search([
                ('user_ids', 'in', [first_user.id if first_user else 2]),
            ], limit=1)
            if not livechat_channel:
                livechat_channel = request.env['im_livechat.channel'].sudo().search([], limit=1)
            if not livechat_channel:
                _logger.error('[Zalo Webhook] No livechat channel configured')
                return
            operator_name = (
                first_user.livechat_username
                or first_user.name
                or 'Nhân viên'
            ) if first_user else 'Nhân viên'
            channel_name = '%s %s' % (partner.name, operator_name)
            if zalo_type == 'group':
                channel_name = 'Zalo Group %s' % thread_id
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
                'name': channel_name,
                'zalo_thread_id': thread_id,
                'zalo_thread_type': zalo_type,
                'zalo_account_id': account.id,
            })
            channel._broadcast([operator.id])
        elif zalo_type == 'group':
            # For group channels, ensure sender partner is a member
            existing_partner_ids = channel.channel_member_ids.mapped('partner_id.id')
            if partner.id not in existing_partner_ids:
                channel.sudo().write({
                    'channel_member_ids': [Command.create({
                        'partner_id': partner.id,
                        'livechat_member_type': 'visitor',
                    })],
                })
        # Parse content & download files
        parsed = self._parse_zalo_content(msg_data)
        body = parsed.get('body', '')
        file_attachments = parsed.get('attachments', [])  # [(name, bytes)]
        # Don't post empty messages (would show as "removed" in Discuss)
        if not body and not file_attachments:
            _logger.warning(
                '[Zalo Webhook] Skipping empty message from %s (msgType=%s)',
                thread_id, msg_data.get('msgType', ''),
            )
            return
        # Post message (with context to prevent forwarding back to Zalo)
        # Use attachments= parameter so Odoo creates & links them properly
        posted = channel.with_context(from_zalo_webhook=True).message_post(
            body=body,
            attachments=file_attachments,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=partner.id,
        )
        # Store Zalo message metadata for future quote/reaction
        zalo_msg_id = str(msg_data.get('msgId', ''))
        if zalo_msg_id and posted:
            quote_data = {
                'content': msg_data.get('content', ''),
                'msgType': msg_data.get('msgType', ''),
                'propertyExt': msg_data.get('propertyExt', {}),
                'uidFrom': msg_data.get('uidFrom', ''),
                'msgId': msg_data.get('msgId', ''),
                'cliMsgId': msg_data.get('cliMsgId', ''),
                'ts': msg_data.get('ts', ''),
                'ttl': msg_data.get('ttl', 0),
            }
            posted.sudo().write({
                'zalo_msg_id': zalo_msg_id,
                'zalo_msg_data': json.dumps(quote_data, ensure_ascii=False),
            })
        body_preview = body if isinstance(body, str) else str(body)[:80]
        att_names = [a[0] for a in file_attachments]
        _logger.info(
            '[Zalo Webhook] Posted to channel %s from %s (zaloMsgId=%s): %s (files: %s)',
            channel.id, thread_id, zalo_msg_id, body_preview, att_names,
        )

    def _handle_zalo_reaction(self, data):
        """Handle incoming Zalo reaction — add reaction to Odoo message."""
        from odoo.addons.livechat_sidebar.models.zalo_account import ZALO_REACTION_TO_EMOJI

        reaction_data = data.get('data', {})
        thread_id = data.get('threadId', '')
        account_id_str = data.get('accountId')

        # reaction_data.content = {rMsg: [{gMsgID, cMsgID, msgType}], rIcon, rType, source}
        content = reaction_data.get('content', {})
        r_icon = content.get('rIcon', '')
        r_msgs = content.get('rMsg', [])
        uid_from = reaction_data.get('uidFrom', '')

        if not r_icon or not r_msgs:
            _logger.info('[Zalo Webhook] Reaction missing icon or rMsg: %s', content)
            return

        # Map Zalo icon to emoji
        emoji = ZALO_REACTION_TO_EMOJI.get(r_icon, r_icon)

        # Find the partner who reacted
        partner = request.env['res.partner'].sudo().search([
            ('zalo_uid', '=', uid_from),
        ], limit=1) if uid_from else None

        if not partner:
            _logger.info('[Zalo Webhook] Reaction from unknown user %s', uid_from)
            return

        # Find the Odoo message(s) that were reacted to
        for r_msg in r_msgs:
            zalo_msg_id = str(r_msg.get('gMsgID', '') or r_msg.get('cMsgID', ''))
            if not zalo_msg_id:
                continue
            odoo_msg = request.env['mail.message'].sudo().search([
                ('zalo_msg_id', '=', zalo_msg_id),
            ], limit=1)
            if not odoo_msg:
                _logger.info('[Zalo Webhook] Reaction target msg not found: zaloMsgId=%s', zalo_msg_id)
                continue
            # Add reaction via Odoo's built-in method
            guest = request.env['mail.guest']
            odoo_msg._message_reaction(emoji, 'add', partner, guest)
            _logger.info(
                '[Zalo Webhook] Reaction %s added to message %s by %s',
                emoji, odoo_msg.id, partner.name,
            )
