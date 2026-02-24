# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    telesale_logo = fields.Binary(
        string="Telesale Logo",
        related='company_id.telesale_logo',
        readonly=False,
    )
    telesale_favicon = fields.Binary(
        string="Favicon",
        related='company_id.telesale_favicon',
        readonly=False,
    )


class ResCompany(models.Model):
    _inherit = 'res.company'

    telesale_logo = fields.Binary(string="Telesale Logo")
    telesale_favicon = fields.Binary(string="Favicon")
