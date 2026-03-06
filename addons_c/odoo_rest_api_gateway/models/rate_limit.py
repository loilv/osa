# -*- coding: utf-8 -*-

import time
from odoo import models, fields, api
from odoo.exceptions import AccessDenied


class RateLimit(models.Model):
    """Tracks API request rates for throttling."""
    _name = 'rate.limit'
    _description = 'Rate Limit Tracker'
    _order = 'last_request desc'
    _rec_name = 'identifier'

    identifier = fields.Char(string='Identifier', required=True, index=True,
                             help='API key hash or IP address')
    identifier_type = fields.Selection([
        ('api_key', 'API Key'),
        ('ip', 'IP Address'),
        ('user', 'User'),
    ], string='Type', required=True, default='api_key')
    requests_this_minute = fields.Integer(string='Requests / Minute', default=0)
    requests_this_hour = fields.Integer(string='Requests / Hour', default=0)
    minute_window_start = fields.Float(string='Minute Window Start', default=0)
    hour_window_start = fields.Float(string='Hour Window Start', default=0)
    blocked_until = fields.Datetime(string='Blocked Until')
    total_blocked = fields.Integer(string='Total Blocked Attempts', default=0)
    last_request = fields.Datetime(string='Last Request')

    @api.model
    def check_rate_limit(self, identifier, max_per_minute=60, max_per_hour=1000):
        """
        Check and enforce rate limits.
        Returns True if request is allowed, raises AccessDenied if blocked.
        """
        now = time.time()
        tracker = self.sudo().search([('identifier', '=', identifier)], limit=1)

        if not tracker:
            tracker = self.sudo().create({
                'identifier': identifier,
                'identifier_type': 'api_key',
                'minute_window_start': now,
                'hour_window_start': now,
                'requests_this_minute': 1,
                'requests_this_hour': 1,
                'last_request': fields.Datetime.now(),
            })
            return True

        # Check if currently blocked
        if tracker.blocked_until and tracker.blocked_until > fields.Datetime.now():
            tracker.sudo().write({'total_blocked': tracker.total_blocked + 1})
            raise AccessDenied(
                f"Rate limit exceeded. Blocked until {tracker.blocked_until}. "
                "Please try again later."
            )

        # Reset minute window if 60s elapsed
        if now - tracker.minute_window_start >= 60:
            tracker.sudo().write({
                'minute_window_start': now,
                'requests_this_minute': 1,
            })
        else:
            if tracker.requests_this_minute >= max_per_minute:
                block_until = fields.Datetime.add(fields.Datetime.now(), minutes=1)
                tracker.sudo().write({
                    'blocked_until': block_until,
                    'total_blocked': tracker.total_blocked + 1,
                })
                raise AccessDenied(
                    f"Rate limit exceeded: {max_per_minute} requests/minute. "
                    f"Blocked until {block_until}."
                )
            tracker.sudo().write({
                'requests_this_minute': tracker.requests_this_minute + 1,
            })

        # Reset hour window if 3600s elapsed
        if now - tracker.hour_window_start >= 3600:
            tracker.sudo().write({
                'hour_window_start': now,
                'requests_this_hour': 1,
            })
        else:
            if tracker.requests_this_hour >= max_per_hour:
                block_until = fields.Datetime.add(fields.Datetime.now(), hours=1)
                tracker.sudo().write({
                    'blocked_until': block_until,
                    'total_blocked': tracker.total_blocked + 1,
                })
                raise AccessDenied(
                    f"Rate limit exceeded: {max_per_hour} requests/hour. "
                    f"Blocked until {block_until}."
                )
            tracker.sudo().write({
                'requests_this_hour': tracker.requests_this_hour + 1,
            })

        tracker.sudo().write({'last_request': fields.Datetime.now(), 'blocked_until': False})
        return True

    @api.model
    def _cron_reset_counters(self):
        """Reset rate limit counters (runs every hour via cron)."""
        self.sudo().search([]).write({
            'requests_this_minute': 0,
            'requests_this_hour': 0,
            'blocked_until': False,
        })
