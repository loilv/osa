from odoo import fields, models

class LostReason(models.Model):
    _inherit = 'crm.lost.reason'

    code = fields.Char(string='Mã')
    active = fields.Boolean(default=True)