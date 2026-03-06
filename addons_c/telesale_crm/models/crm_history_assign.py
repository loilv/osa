from odoo import fields, models

class AssignLeadLine(models.Model):
    _name = 'crm.history.assign'
    _description = 'Lịch sử phân công'
    _order = 'id desc'

    manager_id = fields.Many2one('res.users', string='Người thực hiện')
    user_id = fields.Many2one('res.users', string='Người được phân công')
    crm_campaign_id = fields.Many2one(related='lead_id.crm_campaign_id', string='Chiến dịch')
    lead_id = fields.Many2one('crm.lead', string='Cơ hội')
