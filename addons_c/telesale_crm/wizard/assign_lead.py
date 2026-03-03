from odoo import fields, models
from odoo.exceptions import ValidationError, UserError


class AssignLead(models.TransientModel):
    _name = 'wizard.assign.lead'
    _description = 'Assign Lead'

    type = fields.Selection([
        ('group', 'Nhóm'),
        ('agent', 'Nhân viên'),
        ('rank', 'Cấp bậc')
    ], default='group', string='Chọn loại phân bổ', required=True)
    group_id = fields.Many2one('crm.team', string='Chọn nhóm')
    agent_ids = fields.Many2many('res.users', string='Chọn nhân viên')

    def action_assign(self):
        active_ids = self.env.context.get('active_ids')
        user_ids = self.group_id.member_ids

        if self.type == 'group':
            if not self.group_id:
                raise UserError('Nhóm chưa được chọn!')
            user_ids = [member.id for member in self.group_id.member_ids]
        elif self.type == 'agents':
            if not self.agent_ids:
                raise UserError('Nhân viên chưa được chọn!')
            user_ids = self.agent_ids

        lead_ids = self.env['crm.lead'].search([('id', 'in', active_ids)])

        if not len(user_ids) > 0:
            raise UserError('Không đủ nhân viên để phân bổ!')

        update_vals = {}

        steps = len(user_ids)
        if steps > len(lead_ids):
            raise ValidationError('Số lượng cuộc gọi không đủ để phân bổ!')

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

        return {'type': 'ir.actions.act_window_close'}
