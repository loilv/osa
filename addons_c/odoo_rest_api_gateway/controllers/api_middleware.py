# -*- coding: utf-8 -*-
"""
Security middleware for the REST API Gateway.
Handles JWT validation, API key auth, rate limiting, IP filtering, and request logging.
"""

import time
import json
import hashlib
import logging
import traceback
from functools import wraps

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT Utility
# ---------------------------------------------------------------------------

JWT_SECRET = None
JWT_ALGORITHM = 'HS256'
JWT_ACCESS_EXPIRY = 3600        # 1 hour
JWT_REFRESH_EXPIRY = 86400 * 7  # 7 days


def _get_jwt_secret():
    """Lazy-load the secret; fall back to database UUID."""
    global JWT_SECRET
    if JWT_SECRET is None:
        try:
            import jwt  # noqa: F401
            db_uuid = request.env['ir.config_parameter'].sudo().get_param('database.uuid', 'odoo-rest-api-secret')
            JWT_SECRET = f"odoo-rest-api-{db_uuid}"
        except Exception:
            JWT_SECRET = 'odoo-rest-api-fallback-secret-change-me'
    return JWT_SECRET


def generate_tokens(user_id):
    """Return (access_token, refresh_token) for the given user id."""
    import jwt as pyjwt
    now = int(time.time())
    secret = _get_jwt_secret()

    access_payload = {
        'uid': user_id,
        'type': 'access',
        'iat': now,
        'exp': now + JWT_ACCESS_EXPIRY,
    }
    refresh_payload = {
        'uid': user_id,
        'type': 'refresh',
        'iat': now,
        'exp': now + JWT_REFRESH_EXPIRY,
    }
    access_token = pyjwt.encode(access_payload, secret, algorithm=JWT_ALGORITHM)
    refresh_token = pyjwt.encode(refresh_payload, secret, algorithm=JWT_ALGORITHM)
    return access_token, refresh_token


def decode_token(token, expected_type='access'):
    """Decode and validate a JWT. Returns the payload dict or None."""
    import jwt as pyjwt
    try:
        payload = pyjwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get('type') != expected_type:
            return None
        return payload
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_response(data, status=200):
    """Return a properly formatted JSON response."""
    body = json.dumps(data, default=str)
    return request.make_response(body, headers=[
        ('Content-Type', 'application/json'),
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key'),
    ], status=status)


def _error_response(message, status=400, code=None):
    return _json_response({
        'success': False,
        'error': {
            'code': code or status,
            'message': message,
        },
    }, status=status)


def _get_request_ip():
    try:
        return request.httprequest.environ.get(
            'HTTP_X_FORWARDED_FOR',
            request.httprequest.environ.get('REMOTE_ADDR', '0.0.0.0')
        ).split(',')[0].strip()
    except Exception:
        return '0.0.0.0'


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _log_request(endpoint, method, user_id, api_key_id, status_code,
                 response_time, payload=None, response=None, error=None):
    """Persist request to api.log (non-blocking best-effort)."""
    try:
        request.env['api.log'].sudo().create({
            'endpoint': endpoint,
            'method': method,
            'user_id': user_id,
            'api_key_id': api_key_id,
            'status_code': status_code,
            'response_time': response_time,
            'ip_address': _get_request_ip(),
            'user_agent': request.httprequest.headers.get('User-Agent', '')[:256],
            'request_payload': json.dumps(payload, default=str)[:4096] if payload else '',
            'response_payload': json.dumps(response, default=str)[:4096] if response else '',
            'error_message': str(error)[:2048] if error else '',
        })
        # Increment total_calls on the api key
        if api_key_id:
            key_rec = request.env['api.key'].sudo().browse(api_key_id)
            if key_rec.exists():
                key_rec.write({
                    'total_calls': key_rec.total_calls + 1,
                    'last_used': request.env['api.log']._fields['created_at'].default(request.env['api.log']),
                })
    except Exception:
        _logger.warning("Failed to log API request: %s", traceback.format_exc())


# ---------------------------------------------------------------------------
# Decorator: authenticate & authorize
# ---------------------------------------------------------------------------

def api_auth(scopes=None, methods=None):
    """
    Decorator for API controller methods.
    Checks JWT or API-Key auth, enforces rate limits, IP whitelist, and logs.
    """
    if scopes is None:
        scopes = []
    if methods is None:
        methods = ['GET']

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            endpoint = request.httprequest.path
            method = request.httprequest.method
            user_id = None
            api_key_id = None

            # ---- CORS preflight ----
            if method == 'OPTIONS':
                return _json_response({'status': 'ok'})

            try:
                # ---- 1. Authenticate ----
                auth_header = request.httprequest.headers.get('Authorization', '')
                api_key_header = request.httprequest.headers.get('X-API-Key', '')

                api_key_rec = None

                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                    payload = decode_token(token, expected_type='access')
                    if not payload:
                        return _error_response('Invalid or expired token', 401, 'INVALID_TOKEN')
                    user_id = payload['uid']
                elif api_key_header:
                    api_key_rec = request.env['api.key'].sudo()._validate_key(api_key_header)
                    if not api_key_rec:
                        return _error_response('Invalid API key', 401, 'INVALID_API_KEY')
                    user_id = api_key_rec.user_id.id
                    api_key_id = api_key_rec.id
                else:
                    return _error_response(
                        'Authentication required. Provide Bearer token or X-API-Key header.',
                        401, 'AUTH_REQUIRED'
                    )

                # ---- 2. IP whitelist (API key only) ----
                if api_key_rec and api_key_rec.allowed_ips:
                    allowed = [ip.strip() for ip in api_key_rec.allowed_ips.split(',') if ip.strip()]
                    client_ip = _get_request_ip()
                    if allowed and client_ip not in allowed:
                        return _error_response(
                            f'IP {client_ip} is not allowed for this API key.',
                            403, 'IP_BLOCKED'
                        )

                # ---- 3. Scope check ----
                if scopes and api_key_rec:
                    key_scopes = api_key_rec.scope_ids.mapped('code')
                    for sc in scopes:
                        if sc not in key_scopes:
                            return _error_response(
                                f'Missing required scope: {sc}',
                                403, 'SCOPE_DENIED'
                            )

                # ---- 4. Rate limit ----
                identifier = api_key_rec.key_hash if api_key_rec else f'user_{user_id}'
                max_min = api_key_rec.rate_limit_per_minute if api_key_rec else 60
                max_hr = api_key_rec.rate_limit_per_hour if api_key_rec else 1000
                try:
                    request.env['rate.limit'].sudo().check_rate_limit(identifier, max_min, max_hr)
                except AccessDenied as e:
                    elapsed = round((time.time() - start) * 1000, 2)
                    _log_request(endpoint, method, user_id, api_key_id, 429, elapsed, error=str(e))
                    return _error_response(str(e), 429, 'RATE_LIMITED')

                # ---- 5. Switch to authenticated user environment ----
                if user_id:
                    request.update_env(user=user_id)

                # ---- 6. Execute handler ----
                result = func(*args, **kwargs)

                # ---- 7. Log success ----
                elapsed = round((time.time() - start) * 1000, 2)
                _log_request(endpoint, method, user_id, api_key_id, 200, elapsed)
                return result

            except AccessDenied as e:
                elapsed = round((time.time() - start) * 1000, 2)
                _log_request(endpoint, method, user_id, api_key_id, 403, elapsed, error=str(e))
                return _error_response(str(e), 403, 'ACCESS_DENIED')
            except Exception as e:
                elapsed = round((time.time() - start) * 1000, 2)
                _logger.exception("API Gateway error on %s %s", method, endpoint)
                _log_request(endpoint, method, user_id, api_key_id, 500, elapsed, error=str(e))
                return _error_response(f'Internal server error: {e}', 500, 'SERVER_ERROR')

        return wrapper
    return decorator
