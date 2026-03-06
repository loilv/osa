# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ApiScope(models.Model):
    """Defines permission scopes for API keys (e.g. products:read, orders:write)."""
    _name = 'api.scope'
    _description = 'API Scope'
    _order = 'name'

    name = fields.Char(string='Scope Name', required=True, help='e.g. products:read, orders:write')
    code = fields.Char(string='Code', required=True, help='Machine-readable code, e.g. products_read')
    description = fields.Text(string='Description')
    model_name = fields.Char(string='Model', help='Odoo model this scope applies to, e.g. product.template')
    perm_read = fields.Boolean(string='Read', default=True)
    perm_write = fields.Boolean(string='Write', default=False)
    perm_create = fields.Boolean(string='Create', default=False)
    perm_unlink = fields.Boolean(string='Delete', default=False)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Scope code must be unique!'),
    ]
