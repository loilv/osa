from odoo import fields, models

class LeadCareHistory(models.Model):
    _name = 'crm.lead.care.history'
    _description = 'Lead Care History'
    _order = 'create_date desc'

    lead_id = fields.Many2one('crm.lead', string='Lead')
    call_type = fields.Selection([
        ('out', 'Gọi ra'),
        ('in', 'Gọi vào'),
    ], string='Loại cuộc gọi')
    call_result = fields.Selection([
        ('connected', 'Kết nối thành công'),
        ('no_answer', 'Không trả lời'),
        ('busy', 'Máy bận'),
        ('rejected', 'Từ chối cuộc gọi'),
        ('unreachable', 'Không liên lạc được'),
        ('wrong_number', 'Sai số'),
    ], string='Kết quả kết nối')
    date_callback = fields.Datetime(string='Thời gian gọi lại')
    tag_ids = fields.Many2many('crm.tag', string='Nhãn')
    stage_id = fields.Many2one('crm.stage', string='Trạng thái')
    lost_reason_id = fields.Many2one('crm.lost.reason', 'Lý do thất bại')
    note = fields.Text('Ghi chú')
    user_id = fields.Many2one('res.users', string='Người thực hiện')
    record_url = fields.Char(string='File ghi âm')
    call_log_id = fields.Many2one('asterisk.call.log', string='Cuộc gọi Asterisk', ondelete='set null')

