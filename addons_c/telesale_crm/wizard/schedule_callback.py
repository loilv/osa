from odoo import fields, models
from datetime import datetime, timedelta

class ScheduleCallback(models.TransientModel):
    _name = 'crm.schedule.callback'
    _description = 'ScheduleCallback'

    date = fields.Datetime(string='Thời gian gọi lại', required=True)
    note = fields.Text(string='Ghi chú')

    def action_done(self):
        self.ensure_one()

        active_id = self._context.get('active_id')
        lead = self.env['crm.lead'].search([('id', '=', active_id)])
        if not lead:
            return False

        partner_ids = self.env.user.partner_id.ids
        start = self.date
        stop = self.date + timedelta(minutes=5)
        vals = {
            'opportunity_id': lead.id,
            'partner_id': lead.partner_id.id,
            'partner_ids': partner_ids,
            'name': lead.name,
            'start': start,
            'stop': stop,
            'notes': self.note,
        }
        self.env["calendar.event"].create(vals)
        lead.write({
            'stage_id': self.env.ref('telesale_crm.stage_callback').id,
            'call_back_time': self.date,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Đặt lịch gọi lại thành công!",
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
