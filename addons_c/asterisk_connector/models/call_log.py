# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class AsteriskCallLog(models.Model):
    _name = 'asterisk.call.log'
    _description = 'Lịch sử cuộc gọi'
    _order = 'start_time desc'
    _rec_name = 'display_name'

    asterisk_user_id = fields.Many2one('asterisk.user', string='Asterisk User', 
                                        ondelete='set null')
    user_id = fields.Many2one('res.users', string='Người dùng', 
                               related='asterisk_user_id.user_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Đối tác/Khách hàng')
    
    direction = fields.Selection([
        ('incoming', 'Cuộc gọi đến'),
        ('outgoing', 'Cuộc gọi đi'),
    ], string='Hướng cuộc gọi', required=True)
    
    phone_number = fields.Char(string='Số điện thoại', required=True)
    caller_id = fields.Char(string='Caller ID')
    
    channel = fields.Char(string='Channel')
    unique_id = fields.Char(string='Unique ID')
    linked_id = fields.Char(string='Linked ID')
    
    start_time = fields.Datetime(string='Thời gian bắt đầu', default=fields.Datetime.now)
    answer_time = fields.Datetime(string='Thời gian trả lời')
    end_time = fields.Datetime(string='Thời gian kết thúc')
    
    duration = fields.Integer(string='Thời lượng (giây)', compute='_compute_duration', 
                               store=True)
    duration_display = fields.Char(string='Thời lượng', compute='_compute_duration_display')
    billsec = fields.Integer(string='Thời gian đàm thoại (giây)')
    
    state = fields.Selection([
        ('dialing', 'Đang quay số'),
        ('ringing', 'Đang đổ chuông'),
        ('answered', 'Đã trả lời'),
        ('busy', 'Máy bận'),
        ('no_answer', 'Không trả lời'),
        ('failed', 'Thất bại'),
        ('transferred', 'Đã chuyển'),
        ('hangup', 'Đã kết thúc'),
    ], string='Trạng thái', default='dialing')
    
    transfer_to = fields.Char(string='Chuyển đến')
    recording_url = fields.Char(string='URL ghi âm')
    notes = fields.Text(string='Ghi chú')
    
    display_name = fields.Char(string='Tên hiển thị', compute='_compute_display_name')
    
    company_id = fields.Many2one('res.company', string='Công ty', 
                                  default=lambda self: self.env.company)

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                delta = rec.end_time - rec.start_time
                rec.duration = int(delta.total_seconds())
            else:
                rec.duration = 0

    @api.depends('duration')
    def _compute_duration_display(self):
        for rec in self:
            if rec.duration:
                minutes, seconds = divmod(rec.duration, 60)
                hours, minutes = divmod(minutes, 60)
                if hours:
                    rec.duration_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    rec.duration_display = f"{minutes:02d}:{seconds:02d}"
            else:
                rec.duration_display = "00:00"

    @api.depends('direction', 'phone_number', 'partner_id')
    def _compute_display_name(self):
        for rec in self:
            direction_label = dict(rec._fields['direction'].selection).get(rec.direction, '')
            partner_name = rec.partner_id.name if rec.partner_id else rec.phone_number
            rec.display_name = f"{direction_label}: {partner_name}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Tự động tìm partner từ số điện thoại
            if vals.get('phone_number') and not vals.get('partner_id'):
                partner = self._find_partner_by_phone(vals['phone_number'])
                if partner:
                    vals['partner_id'] = partner.id
        return super().create(vals_list)

    def _find_partner_by_phone(self, phone_number):
        """Tìm partner từ số điện thoại — ưu tiên phone_sanitized (indexed) cho performance."""
        if not phone_number:
            return False

        clean_number = ''.join(filter(str.isdigit, phone_number))
        if not clean_number:
            return False

        Partner = self.env['res.partner']
        last9 = clean_number[-9:] if len(clean_number) >= 9 else clean_number

        # Ưu tiên phone_sanitized nếu field tồn tại (phone_validation module)
        if 'phone_sanitized' in Partner._fields:
            if clean_number.startswith('0') and len(clean_number) >= 10:
                sanitized = '+84' + clean_number[1:]
            elif clean_number.startswith('84') and len(clean_number) >= 11:
                sanitized = '+' + clean_number
            else:
                sanitized = '+84' + last9

            partner = Partner.search([
                ('phone_sanitized', '=', sanitized),
            ], limit=1)
            if partner:
                return partner

        # Fallback: ilike last 9 digits trên phone
        partner = Partner.search([
            ('phone', 'ilike', last9),
        ], limit=1)

        return partner

    def action_view_partner(self):
        """Mở form partner"""
        self.ensure_one()
        if self.partner_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False

    def action_create_partner(self):
        """Tạo partner mới từ số điện thoại"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_phone': self.phone_number,
                'default_name': f'Khách hàng - {self.phone_number}',
            },
        }

    def action_callback(self):
        """Gọi lại số điện thoại"""
        self.ensure_one()
        if self.asterisk_user_id:
            return self.asterisk_user_id.make_call(self.phone_number)
        return False

    @api.model
    def create_incoming_call(self, data):
        """Tạo log cuộc gọi đến từ AMI event"""
        asterisk_user = self.env['asterisk.user'].search([
            ('extension', '=', data.get('extension')),
        ], limit=1)
        
        vals = {
            'direction': 'incoming',
            'phone_number': data.get('caller_id_num', data.get('phone_number', '')),
            'caller_id': data.get('caller_id_name', ''),
            'channel': data.get('channel', ''),
            'unique_id': data.get('unique_id', ''),
            'linked_id': data.get('linked_id', ''),
            'state': 'ringing',
        }
        
        if asterisk_user:
            vals['asterisk_user_id'] = asterisk_user.id
        
        return self.create(vals)

    @api.model
    def update_call_state(self, unique_id, state, **kwargs):
        """Cập nhật trạng thái cuộc gọi từ AMI event.
        Tìm call_log theo unique_id trước, fallback sang linked_id,
        rồi fallback sang channel nếu có.
        """
        call_log = self.search([('unique_id', '=', unique_id)], limit=1)
        if not call_log and unique_id:
            call_log = self.search([('linked_id', '=', unique_id)], limit=1)

        # Fallback: tìm theo channel nếu có (cho trường hợp unique_id chưa được link)
        if not call_log and kwargs.get('channel'):
            call_log = self.search([
                ('channel', '=', kwargs['channel']),
                ('state', 'not in', ['hangup', 'failed']),
            ], limit=1, order='id desc')
            # Nếu tìm được, cập nhật luôn unique_id/linked_id
            if call_log and unique_id:
                link_vals = {'unique_id': unique_id}
                if kwargs.get('linked_id'):
                    link_vals['linked_id'] = kwargs['linked_id']
                call_log.write(link_vals)
                _logger.info('Linked unique_id %s to call_log %s via channel fallback', unique_id, call_log.id)

        if call_log:
            vals = {'state': state}
            
            if state == 'answered' and not call_log.answer_time:
                vals['answer_time'] = fields.Datetime.now()
            elif state in ('hangup', 'no_answer', 'busy', 'failed'):
                vals['end_time'] = fields.Datetime.now()
            
            if kwargs.get('billsec'):
                vals['billsec'] = kwargs['billsec']
            if kwargs.get('recording_url'):
                vals['recording_url'] = kwargs['recording_url']
                
            call_log.write(vals)
            return call_log
        return False
