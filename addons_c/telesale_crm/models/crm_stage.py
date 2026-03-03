from odoo import fields, models

class InheritCrmStage(models.Model):
    _inherit = 'crm.stage'

    is_new = fields.Boolean(string="Là Mới")
    active = fields.Boolean(default=True)