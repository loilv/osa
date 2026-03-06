from odoo import models, fields, api
from odoo.exceptions import UserError


class CrmCampaignAssignWizard(models.TransientModel):
    _name = 'crm.campaign.assign.wizard'
    _description = 'Phân chia cơ hội theo điều kiện'

    state = fields.Selection([
        ('all', 'Tất cả'),
        ('draft', 'Mới'),
        ('open', 'Đang xử lý'),
        ('done', 'Hoàn thành'),
    ], string='Trạng thái', default='all', required=True)

    user_filter_id = fields.Many2one('res.users', string='Người phụ trách')

    distribute_type = fields.Selection([
        ('equal', 'Đồng đều'),
    ], string='Cách phân', default='equal', required=True)

    type = fields.Selection([
        ('group', 'Nhóm'),
        ('agent', 'Nhân viên'),
        ('rank', 'Cấp bậc')
    ], default='group', string='Chọn loại phân bổ', required=True)
    group_id = fields.Many2one('crm.team', string='Chọn nhóm')
    agent_ids = fields.Many2many('res.users', string='Chọn nhân viên')

    def action_assign(self):
        user_ids = self.group_id.member_ids
        active_id = self.env.context.get('active_id')
        campaign_id = self.env['crm.campaign'].browse(active_id)
        filter_domain = [('crm_campaign_id', '=', campaign_id.id)]

        if self.user_filter_id:
            filter_domain.append([('user_id', '=', self.user_filter_id.id)])
        if self.state == 'draft':
            filter_domain.append([('stage_id', '=', self.env.ref('telesale_crm.stage_new').id)])
        if self.state == 'open':
            stage_ids = [self.env.ref('telesale_crm.stage_callback').id,  self.env.ref('telesale_crm.stage_consultant').id]
            filter_domain.append([('stage_id', 'in', stage_ids)])
        if self.state == 'done':
            filter_domain.append([('stage_id', '=', self.env.ref('telesale_crm.stage_success').id)])

        if self.type == 'group':
            if not self.group_id:
                raise UserError('Nhóm chưa được chọn!')
            user_ids = [member.id for member in self.group_id.member_ids]
        elif self.type == 'agents':
            if not self.agent_ids:
                raise UserError('Nhân viên chưa được chọn!')
            user_ids = self.agent_ids

        lead_ids = self.env['crm.lead'].search(domain=filter_domain)

        if not len(user_ids) > 0:
            raise UserError('Không đủ nhân viên để phân bổ!')

        update_vals = {}

        steps = len(user_ids)
        if steps > len(lead_ids):
            raise UserError('Số lượng cuộc gọi không đủ để phân bổ!')

        for idx in range(0, steps):
            subset_ids = lead_ids[idx:len(lead_ids):steps]
            update_vals['user_id'] = user_ids[idx]
            assign_history = [
                (0, 0, {
                    'manager_id': self.env.user.id,
                    'user_id': user_ids[idx]
                })
            ]
            for lead in subset_ids:
                update_vals.update({
                    'assign_history_ids': assign_history
                })
                lead.write(update_vals)