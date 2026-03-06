# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ApiLog(models.Model):
    """Logs every API request for analytics and auditing."""
    _name = 'api.log'
    _description = 'API Request Log'
    _order = 'created_at desc'
    _rec_name = 'endpoint'

    endpoint = fields.Char(string='Endpoint', required=True, index=True)
    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('OPTIONS', 'OPTIONS'),
    ], string='HTTP Method', required=True)
    user_id = fields.Many2one('res.users', string='User', index=True)
    api_key_id = fields.Many2one('api.key', string='API Key', index=True)
    status_code = fields.Integer(string='Status Code')
    response_time = fields.Float(string='Response Time (ms)', digits=(10, 2))
    ip_address = fields.Char(string='IP Address', index=True)
    user_agent = fields.Char(string='User Agent')
    request_payload = fields.Text(string='Request Payload')
    response_payload = fields.Text(string='Response Payload')
    error_message = fields.Text(string='Error Message')
    created_at = fields.Datetime(string='Timestamp', default=fields.Datetime.now, index=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # Computed fields for dashboard
    is_success = fields.Boolean(string='Success', compute='_compute_is_success', store=True)
    date_only = fields.Date(string='Date', compute='_compute_date_only', store=True)

    @api.depends('status_code')
    def _compute_is_success(self):
        for rec in self:
            rec.is_success = 200 <= (rec.status_code or 0) < 400

    @api.depends('created_at')
    def _compute_date_only(self):
        for rec in self:
            rec.date_only = rec.created_at.date() if rec.created_at else False

    @api.model
    def _cron_cleanup_old_logs(self):
        """Remove logs older than 90 days."""
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=90)
        old_logs = self.search([('created_at', '<', cutoff)])
        old_logs.unlink()

    @api.model
    def _get_dashboard_data(self):
        """Return aggregated data for the API dashboard."""
        self.env.cr.execute("""
            SELECT
                COUNT(*) AS total_calls,
                COUNT(*) FILTER (WHERE is_success = TRUE) AS success_calls,
                COUNT(*) FILTER (WHERE is_success = FALSE) AS failed_calls,
                ROUND(AVG(response_time)::numeric, 2) AS avg_response_time,
                COUNT(DISTINCT ip_address) AS unique_ips,
                COUNT(DISTINCT user_id) AS unique_users
            FROM api_log
            WHERE created_at >= NOW() - INTERVAL '30 days'
        """)
        row = self.env.cr.dictfetchone()

        # Top endpoints
        self.env.cr.execute("""
            SELECT endpoint, method, COUNT(*) AS call_count,
                   ROUND(AVG(response_time)::numeric, 2) AS avg_time
            FROM api_log
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY endpoint, method
            ORDER BY call_count DESC
            LIMIT 10
        """)
        top_endpoints = self.env.cr.dictfetchall()

        # Daily calls (last 30 days)
        self.env.cr.execute("""
            SELECT date_only AS date, COUNT(*) AS calls,
                   COUNT(*) FILTER (WHERE is_success = TRUE) AS success,
                   COUNT(*) FILTER (WHERE is_success = FALSE) AS failed
            FROM api_log
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY date_only
            ORDER BY date_only
        """)
        daily_stats = self.env.cr.dictfetchall()

        # Top IPs
        self.env.cr.execute("""
            SELECT ip_address, COUNT(*) AS call_count
            FROM api_log
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY ip_address
            ORDER BY call_count DESC
            LIMIT 10
        """)
        top_ips = self.env.cr.dictfetchall()

        # Serialize dates
        for d in daily_stats:
            d['date'] = str(d['date']) if d.get('date') else ''

        return {
            'summary': row or {},
            'top_endpoints': top_endpoints,
            'daily_stats': daily_stats,
            'top_ips': top_ips,
        }
