# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AsteriskUserStatusLog(models.Model):
    _name = 'asterisk.user.status.log'
    _description = 'Agent Status Change Log'
    _order = 'create_date desc'

    asterisk_user_id = fields.Many2one('asterisk.user', string='Agent', required=True)
    user_id = fields.Many2one('res.users', string='User', related='asterisk_user_id.user_id', store=True)
    old_status = fields.Selection([
        ('ready', 'Sẵn sàng'),
        ('personal_work', 'Làm việc riêng'),
        ('zalo_chat', 'Chat Zalo'),
        ('create_order', 'Tạo đơn'),
        ('check_order', 'Check đơn'),
        ('training', 'Học Đào tạo'),
        ('team_meeting', 'Họp nhóm'),
        ('offline', 'Offline'),
    ], string='Old Status')

    new_status = fields.Selection([
        ('ready', 'Sẵn sàng'),
        ('personal_work', 'Làm việc riêng'),
        ('zalo_chat', 'Chat Zalo'),
        ('create_order', 'Tạo đơn'),
        ('check_order', 'Check đơn'),
        ('training', 'Học Đào tạo'),
        ('team_meeting', 'Họp nhóm'),
        ('offline', 'Offline'),
    ], string='New Status', required=True)
    duration = fields.Float(string='Duration (minutes)', help='Duration in previous status')
    reason = fields.Char(string='Reason/Note')
    create_date = fields.Datetime(string='Change Time', readonly=True, default=fields.Datetime.now)

    @api.depends('asterisk_user_id', 'old_status', 'new_status')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.asterisk_user_id.extension}: {record.old_status or '-'} → {record.new_status}"
