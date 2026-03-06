from odoo import api, fields, models


class CrmCampaign(models.Model):
    _name = 'crm.campaign'
    _description = 'CRM Campaign'

    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('active', 'Hoạt động'),
        ('done', 'Đóng'),
    ], string='Trạng thái', default='draft', tracking=True)
    name = fields.Char(string='Tên chiến dịch', required=True)
    start_date = fields.Datetime(
        string='Ngày bắt đầu',
        required=True
    )
    end_date = fields.Datetime(
        string='Ngày kết thúc',
        required=True
    )
    opportunity_type = fields.Selection(
        [
            ('renew', 'Tái tục'),
            ('new', 'Mới'),
            ('combined', 'Tổng hợp')
        ],
        string='Loại cơ hội',
    )
    note = fields.Text(string='Ghi chú')
    lead_ids = fields.One2many('crm.lead', 'crm_campaign_id', string='Cơ hội')

    def manual_assign(self):
        return {
            'name': 'Cơ hội',
            'view_mode': 'list',
            'res_model': 'crm.lead',
            'domain': [('id', 'in', self.lead_ids.ids)],
            'type': 'ir.actions.act_window',
        }
