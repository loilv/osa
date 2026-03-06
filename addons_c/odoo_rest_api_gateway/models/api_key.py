# -*- coding: utf-8 -*-

import secrets
import hashlib
from odoo import models, fields, api


class ApiKey(models.Model):
    """API Key for authenticating external applications."""
    _name = 'api.key'
    _description = 'API Key'
    _order = 'create_date desc'

    name = fields.Char(string='Application Name', required=True, help='e.g. Mobile App, Website, POS')
    key = fields.Char(
        string='API Key', readonly=True, copy=False,
        help='Auto-generated secret key. Store safely — shown only once.',
    )
    key_hash = fields.Char(string='Key Hash', readonly=True, copy=False, index=True)
    user_id = fields.Many2one('res.users', string='Linked User', required=True,
                              default=lambda self: self.env.user,
                              help='Requests authenticated with this key run as this user.')
    scope_ids = fields.Many2many('api.scope', string='Scopes',
                                 help='Permissions granted to this key.')
    rate_limit_per_minute = fields.Integer(string='Rate Limit / min', default=60)
    rate_limit_per_hour = fields.Integer(string='Rate Limit / hour', default=1000)
    active = fields.Boolean(default=True)
    allowed_ips = fields.Text(string='Allowed IPs',
                              help='Comma-separated list of allowed IPs. Leave empty to allow all.')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    expiration_date = fields.Date(string='Expiration Date')
    last_used = fields.Datetime(string='Last Used', readonly=True)
    total_calls = fields.Integer(string='Total Calls', readonly=True, default=0)
    description = fields.Text(string='Notes')
    state = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ], string='Status', compute='_compute_state', store=True)

    @api.depends('active', 'expiration_date')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active:
                rec.state = 'revoked'
            elif rec.expiration_date and rec.expiration_date < today:
                rec.state = 'expired'
            else:
                rec.state = 'active'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('key'):
                raw_key = secrets.token_urlsafe(48)
                vals['key'] = raw_key
                vals['key_hash'] = hashlib.sha256(raw_key.encode()).hexdigest()
        return super().create(vals_list)

    def action_regenerate_key(self):
        """Regenerate API key."""
        for rec in self:
            raw_key = secrets.token_urlsafe(48)
            rec.write({
                'key': raw_key,
                'key_hash': hashlib.sha256(raw_key.encode()).hexdigest(),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'API Key Regenerated',
                'message': 'New key generated. Copy it now — it won\'t be shown again.',
                'type': 'warning',
                'sticky': True,
            },
        }

    def action_revoke(self):
        self.write({'active': False})

    @api.model
    def _validate_key(self, raw_key):
        """Validate an API key and return the record if valid."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = self.sudo().search([
            ('key_hash', '=', key_hash),
            ('active', '=', True),
        ], limit=1)
        if not api_key:
            return False
        today = fields.Date.context_today(self)
        if api_key.expiration_date and api_key.expiration_date < today:
            return False
        return api_key
