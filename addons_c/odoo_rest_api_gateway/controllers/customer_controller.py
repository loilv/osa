# -*- coding: utf-8 -*-
"""
Customer (res.partner) API – CRUD endpoints for contacts.
"""

import json
import logging

from odoo import http
from odoo.http import request

from .api_middleware import api_auth, _json_response, _error_response

_logger = logging.getLogger(__name__)

CUSTOMER_FIELDS = [
    'id', 'name', 'email', 'phone', 'mobile', 'street', 'street2',
    'city', 'zip', 'country_id', 'state_id', 'vat', 'website',
    'company_type', 'is_company', 'active', 'image_128',
]


def _serialize_customer(partner, fields=None):
    allowed = fields or CUSTOMER_FIELDS
    data = {}
    for f in allowed:
        if f not in partner._fields:
            continue
        val = partner[f]
        field_obj = partner._fields[f]
        if field_obj.type == 'many2one' and val:
            data[f] = {'id': val.id, 'name': val.display_name}
        elif field_obj.type == 'binary' and val:
            data[f] = val.decode('utf-8') if isinstance(val, bytes) else val
        else:
            data[f] = val
    return data


class CustomerController(http.Controller):

    # ------------------------------------------ GET /customers
    @http.route('/api/v1/customers', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth(scopes=['customers_read'])
    def list_customers(self, **kw):
        page = int(kw.get('page', 1))
        limit = min(int(kw.get('limit', 20)), 100)
        offset = (page - 1) * limit

        domain = [('active', '=', True)]

        search = kw.get('search')
        if search:
            domain += ['|', '|',
                        ('name', 'ilike', search),
                        ('email', 'ilike', search),
                        ('phone', 'ilike', search)]

        is_company = kw.get('is_company')
        if is_company is not None:
            domain.append(('is_company', '=', is_company in ('1', 'true', 'True')))

        country_id = kw.get('country_id')
        if country_id:
            domain.append(('country_id', '=', int(country_id)))

        order = kw.get('order', 'name asc')

        Partner = request.env['res.partner'].sudo()
        total = Partner.search_count(domain)
        partners = Partner.search(domain, limit=limit, offset=offset, order=order)

        req_fields = None
        if kw.get('fields'):
            req_fields = [f.strip() for f in kw['fields'].split(',')]
            req_fields = [f for f in req_fields if f in CUSTOMER_FIELDS]

        return _json_response({
            'success': True,
            'data': [_serialize_customer(p, req_fields) for p in partners],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit if limit else 1,
            },
        })

    # ------------------------------------------ GET /customers/<id>
    @http.route('/api/v1/customers/<int:partner_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth(scopes=['customers_read'])
    def get_customer(self, partner_id, **kw):
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return _error_response('Customer not found', 404)
        return _json_response({
            'success': True,
            'data': _serialize_customer(partner),
        })

    # ------------------------------------------ POST /customers
    @http.route('/api/v1/customers', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    @api_auth(scopes=['customers_write'])
    def create_customer(self, **kw):
        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        if not body.get('name'):
            return _error_response('name is required', 400)

        writable = ['name', 'email', 'phone', 'mobile', 'street', 'street2',
                     'city', 'zip', 'country_id', 'state_id', 'vat', 'website',
                     'company_type', 'is_company']
        vals = {k: v for k, v in body.items() if k in writable}

        partner = request.env['res.partner'].sudo().create(vals)

        return _json_response({
            'success': True,
            'data': _serialize_customer(partner),
            'message': 'Customer created successfully',
        }, status=201)

    # ------------------------------------------ PUT /customers/<id>
    @http.route('/api/v1/customers/<int:partner_id>', type='http', auth='none',
                methods=['PUT', 'PATCH'], csrf=False, cors='*')
    @api_auth(scopes=['customers_write'])
    def update_customer(self, partner_id, **kw):
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return _error_response('Customer not found', 404)

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        writable = ['name', 'email', 'phone', 'mobile', 'street', 'street2',
                     'city', 'zip', 'country_id', 'state_id', 'vat', 'website',
                     'company_type', 'is_company']
        vals = {k: v for k, v in body.items() if k in writable}

        if vals:
            partner.write(vals)

        return _json_response({
            'success': True,
            'data': _serialize_customer(partner),
            'message': 'Customer updated successfully',
        })

    # ------------------------------------------ DELETE /customers/<id>
    @http.route('/api/v1/customers/<int:partner_id>', type='http', auth='none',
                methods=['DELETE'], csrf=False, cors='*')
    @api_auth(scopes=['customers_write'])
    def delete_customer(self, partner_id, **kw):
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return _error_response('Customer not found', 404)
        partner.write({'active': False})
        return _json_response({
            'success': True,
            'message': 'Customer archived successfully',
        })
