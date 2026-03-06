# -*- coding: utf-8 -*-
"""
Authentication controller – JWT login, refresh, logout, and user info.
"""

import json
import time
import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied

from .api_middleware import (
    generate_tokens, decode_token, _json_response, _error_response,
    _get_request_ip, _log_request, api_auth,
)

_logger = logging.getLogger(__name__)


class AuthController(http.Controller):

    # ------------------------------------------------------------------ login
    @http.route('/api/v1/auth/login', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def login(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return _json_response({'status': 'ok'})

        start = time.time()
        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        email = body.get('email') or body.get('login', '')
        password = body.get('password', '')
        db = body.get('db') or request.db

        if not email or not password:
            return _error_response('Email and password are required', 400)

        try:
            credential = {
                'login': email,
                'password': password,
                'type': 'password',
            }
            auth_info = request.session.authenticate(request.env, credential)
            uid = auth_info.get('uid')
        except AccessDenied:
            elapsed = round((time.time() - start) * 1000, 2)
            _log_request('/api/v1/auth/login', 'POST', None, None, 401, elapsed,
                         payload={'email': email}, error='Invalid credentials')
            return _error_response('Invalid email or password', 401, 'AUTH_FAILED')
        except Exception as e:
            _logger.exception("Login error")
            return _error_response(f'Login error: {e}', 500)

        if not uid:
            return _error_response('Invalid email or password', 401, 'AUTH_FAILED')

        access_token, refresh_token = generate_tokens(uid)

        user = request.env['res.users'].sudo().browse(uid)
        elapsed = round((time.time() - start) * 1000, 2)
        _log_request('/api/v1/auth/login', 'POST', uid, None, 200, elapsed,
                      payload={'email': email})

        return _json_response({
            'success': True,
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': 3600,
                'token_type': 'Bearer',
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.login,
                    'company_id': user.company_id.id,
                    'company_name': user.company_id.name,
                },
            },
        })

    # -------------------------------------------------------------- refresh
    @http.route('/api/v1/auth/refresh', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def refresh(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return _json_response({'status': 'ok'})

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        refresh_token = body.get('refresh_token', '')
        if not refresh_token:
            return _error_response('refresh_token is required', 400)

        payload = decode_token(refresh_token, expected_type='refresh')
        if not payload:
            return _error_response('Invalid or expired refresh token', 401, 'INVALID_REFRESH')

        uid = payload['uid']
        new_access, new_refresh = generate_tokens(uid)

        return _json_response({
            'success': True,
            'data': {
                'access_token': new_access,
                'refresh_token': new_refresh,
                'expires_in': 3600,
                'token_type': 'Bearer',
            },
        })

    # ---------------------------------------------------------------- whoami
    @http.route('/api/v1/auth/me', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth()
    def me(self, **kw):
        user = request.env.user
        return _json_response({
            'success': True,
            'data': {
                'id': user.id,
                'name': user.name,
                'email': user.login,
                'company_id': user.company_id.id,
                'company_name': user.company_id.name,
                'lang': user.lang,
                'tz': user.tz,
                'groups': user.group_ids.mapped('full_name'),
            },
        })

    # --------------------------------------------------------------- logout
    @http.route('/api/v1/auth/logout', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def logout(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return _json_response({'status': 'ok'})
        request.session.logout()
        return _json_response({
            'success': True,
            'message': 'Logged out successfully',
        })
