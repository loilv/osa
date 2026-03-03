import logging

from odoo import Command, fields, models, api

_logger = logging.getLogger(__name__)


class ZaloChatWizard(models.TransientModel):
    _name = 'zalo.chat.wizard'
    _description = 'Zalo Chat Wizard'

    lead_id = fields.Many2one('crm.lead', string='Lead', readonly=True)
    phone = fields.Char(string='Số điện thoại', readonly=True)
    lead_name = fields.Char(string='Tên khách hàng', readonly=True)

    # Zalo info (populated by _zalo_lookup)
    zalo_id = fields.Char(string='Zalo ID', readonly=True)
    zalo_display_name = fields.Char(string='Tên Zalo', readonly=True)
    zalo_avatar_url = fields.Char(string='Avatar URL', readonly=True)
    lookup_done = fields.Boolean(default=False, readonly=True)
    error_message = fields.Char(string='Lỗi', readonly=True)

    # Friend request
    friend_message = fields.Text(
        string='Nội dung lời mời',
        default='Xin chào! Tôi muốn kết bạn với bạn.',
    )
    friend_request_sent = fields.Boolean(default=False, readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            lead = self.env['crm.lead'].browse(active_id)
            res['lead_id'] = lead.id
            res['phone'] = lead.phone or ''
            res['lead_name'] = lead.partner_name or lead.contact_name or ''
            # Auto-lookup Zalo info
            if lead.phone:
                zalo_data = self._zalo_lookup(lead.phone)
                res.update(zalo_data)
        return res

    def _get_zalo_account(self):
        ZaloAccount = self.env.get('zalo.account')
        if ZaloAccount is None:
            return None
        account = ZaloAccount.sudo().search([
            ('user_ids', 'in', [self.env.uid]),
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

    @api.model
    def _zalo_lookup(self, phone):
        """Look up Zalo user info by phone. Returns dict of field values."""
        result = {
            'lookup_done': True,
            'error_message': False,
            'zalo_id': False,
            'zalo_display_name': False,
            'zalo_avatar_url': False,
        }
        phone = (phone or '').strip()
        if not phone:
            result['error_message'] = 'Số điện thoại trống.'
            return result

        ZaloAccount = self.env.get('zalo.account')
        if ZaloAccount is None:
            result['error_message'] = 'Module Zalo chưa được cài đặt.'
            return result

        account = ZaloAccount.sudo().search([
            ('user_ids', 'in', [self.env.uid]),
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
        if not account:
            result['error_message'] = 'Không tìm thấy tài khoản Zalo đã kết nối.'
            return result

        try:
            find_result = account._call_bridge(
                'find-user', method='POST', data={'phone': phone},
            )
            if not find_result.get('success'):
                result['error_message'] = find_result.get('error', 'Không tìm thấy người dùng Zalo.')
                return result

            user_data = find_result.get('data', {})
            uid = user_data.get('uid', '')
            result['zalo_id'] = uid
            result['zalo_display_name'] = (
                user_data.get('display_name', '')
                or user_data.get('zalo_name', '')
            )
            result['zalo_avatar_url'] = user_data.get('avatar', '')
        except Exception as e:
            _logger.error('Zalo lookup failed for %s: %s', phone, e)
            result['error_message'] = str(e)
        return result

    def action_send_friend_request(self):
        """Send Zalo friend request with custom message."""
        self.ensure_one()
        account = self._get_zalo_account()
        if not account:
            self.write({'error_message': 'Không tìm thấy tài khoản Zalo đã kết nối.'})
            return self._reopen()

        msg = (self.friend_message or '').strip() or 'Xin chào! Tôi muốn kết bạn với bạn.'
        try:
            if not self.zalo_id:
                find_result = account._call_bridge(
                    'find-user', method='POST', data={'phone': self.phone},
                )
                if not find_result.get('success'):
                    self.write({'error_message': 'Không tìm thấy người dùng Zalo.'})
                    return self._reopen()
                self.zalo_id = find_result.get('data', {}).get('uid', '')

            result = account._call_bridge(
                'send-friend-request',
                method='POST',
                data={'userId': self.zalo_id, 'msg': msg},
            )
            if result.get('success'):
                self.write({'friend_request_sent': True, 'error_message': False})
                _logger.info('Zalo friend request sent to %s (uid: %s)', self.phone, self.zalo_id)
            else:
                self.write({'error_message': result.get('error', 'Gửi lời mời thất bại.')})
        except Exception as e:
            _logger.error('Zalo friend request failed: %s', e)
            self.write({'error_message': str(e)})
        return self._reopen()

    def _reopen(self):
        """Return action to reopen this wizard (refresh the form)."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
