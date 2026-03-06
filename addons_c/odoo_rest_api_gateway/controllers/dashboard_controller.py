# -*- coding: utf-8 -*-
"""
Dashboard JSON controller – serves analytics data to the OWL frontend.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DashboardController(http.Controller):

    @http.route('/api/gateway/dashboard/data', type='http', auth='user',
                methods=['GET'], csrf=False)
    def dashboard_data(self, **kw):
        """Return aggregated API statistics for the backend dashboard."""
        data = request.env['api.log'].sudo()._get_dashboard_data()
        body = json.dumps(data, default=str)
        return request.make_response(body, headers=[('Content-Type', 'application/json')])
