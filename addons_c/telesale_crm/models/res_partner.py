from typing import Self

from odoo import fields, models
from odoo.orm.types import ValuesType


class InheritPartner(models.Model):
    _inherit = 'res.partner'

    date_of_birth = fields.Date(string='Ngày sinh')
    gender = fields.Selection([
        ('male', 'Nam'),
        ('female', 'Nữ'),
    ], string='Giới tính')


class InheirtDC(models.Model):
    _inherit = 'discuss.channel'


    def create(self, vals_list):
        res = super(InheirtDC, self).create(vals_list)
        return res