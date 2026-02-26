from odoo import fields, models

class LeadCareHistory(models.Model):
    _name = 'crm.lead.care.history'
    _description = 'Lead Care History'

    lead_id = fields.Many2one('crm.lead', string='Lead')
    call_type = fields.Selection([
        ('out', 'Gọi ra'),
        ('in', 'Gọi vào'),
    ], string='Loại cuộc gọi')
    tag_ids = fields.Many2many('crm.tag', string='Tags')
    note = fields.Text('Ghi chú')
    user_id = fields.Many2one('res.users', string='Người thực hiện')
    record_url = fields.Char(string='File ghi âm')
    call_log_id = fields.Many2one('asterisk.call.log', string='Cuộc gọi Asterisk', ondelete='set null')

