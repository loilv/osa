from odoo import fields, models

class LostReasonPopup(models.TransientModel):
    _name = 'crm.lost.reason.wizard'

    lost_reason_id = fields.Many2one('crm.lost.reason', string='Lý do mất')
    lost_reason_code = fields.Char(related='lost_reason_id.code', readonly=True)
    note = fields.Text(string='Ghi chú')
    date_insurance = fields.Date(string="Ngày hết hạn bảo hiểm")

    def action_done(self):
        self.ensure_one()

        active_id = self._context.get('active_id')
        lead = self.env['crm.lead'].browse(active_id)
        lead.write({
            'lost_reason_id': self.lost_reason_id.id,
            'date_insurance': self.date_insurance,
            'stage_note': self.note,
            'probability': 0,
            'active': False,
            'stage_id': self.env.ref('telesale_crm.stage_lost').id,
        })
