# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    asterisk_preferred_extension = fields.Char(string='Extension ưu tiên')
    asterisk_preferred_call_type = fields.Selection([
        ('softphone', 'Softphone (WebRTC)'),
        ('ipphone', 'IP Phone'),
    ], string='Loại cuộc gọi ưu tiên', default='softphone')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    call_log_ids = fields.One2many('asterisk.call.log', 'partner_id', 
                                    string='Lịch sử cuộc gọi')
    call_count = fields.Integer(string='Số cuộc gọi', compute='_compute_call_count')

    @api.depends('call_log_ids')
    def _compute_call_count(self):
        for partner in self:
            partner.call_count = len(partner.call_log_ids)

    def action_make_call(self):
        """Thực hiện cuộc gọi tới partner"""
        self.ensure_one()
        phone = self.phone
        if not phone:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi',
                    'message': 'Partner không có số điện thoại',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        asterisk_user = self.env['asterisk.user'].search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ], limit=1)
        
        if not asterisk_user:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi',
                    'message': 'Bạn chưa được cấu hình extension Asterisk',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        result = asterisk_user.make_call(phone)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đang gọi',
                'message': f'Đang thực hiện cuộc gọi tới {phone}',
                'type': 'info',
                'sticky': False,
            }
        }

    def action_view_calls(self):
        """Xem lịch sử cuộc gọi của partner"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lịch sử cuộc gọi - {self.name}',
            'res_model': 'asterisk.call.log',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
