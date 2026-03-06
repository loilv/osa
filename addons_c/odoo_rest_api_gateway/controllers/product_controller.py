# -*- coding: utf-8 -*-
"""
Product API – RESTful endpoints for product.template & product.product.
"""

import json
import logging

from odoo import http
from odoo.http import request

from .api_middleware import api_auth, _json_response, _error_response

_logger = logging.getLogger(__name__)

# Allowed fields exposed via the API (whitelist for security)
PRODUCT_FIELDS = [
    'id', 'name', 'default_code', 'barcode', 'list_price', 'standard_price',
    'categ_id', 'type', 'uom_id', 'description_sale', 'qty_available',
    'virtual_available', 'active', 'image_128',
]


def _serialize_product(product, fields=None):
    """Convert a product record to a JSON-safe dict."""
    allowed = fields or PRODUCT_FIELDS
    data = {}
    for f in allowed:
        if f not in product._fields:
            continue
        val = product[f]
        field_obj = product._fields[f]
        if field_obj.type == 'many2one' and val:
            data[f] = {'id': val.id, 'name': val.display_name}
        elif field_obj.type in ('one2many', 'many2many'):
            data[f] = [{'id': r.id, 'name': r.display_name} for r in val]
        elif field_obj.type == 'binary' and val:
            data[f] = val.decode('utf-8') if isinstance(val, bytes) else val
        elif field_obj.type in ('date', 'datetime') and val:
            data[f] = str(val)
        else:
            data[f] = val
    return data


class ProductController(http.Controller):

    # ----------------------------------------------------- GET /products
    @http.route('/api/v1/products', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth(scopes=['products_read'])
    def list_products(self, **kw):
        """
        GET /api/v1/products
        Query params:
          page (int)   – page number, default 1
          limit (int)  – records per page, default 20, max 100
          search (str) – name / default_code search
          category (int) – categ_id filter
          min_price / max_price (float)
          fields (str) – comma-separated field list
          order (str)  – e.g. list_price asc
        """
        page = int(kw.get('page', 1))
        limit = min(int(kw.get('limit', 20)), 100)
        offset = (page - 1) * limit

        domain = [('active', '=', True)]

        search = kw.get('search')
        if search:
            domain += ['|', ('name', 'ilike', search), ('default_code', 'ilike', search)]

        category = kw.get('category')
        if category:
            domain.append(('categ_id', '=', int(category)))

        min_price = kw.get('min_price')
        if min_price:
            domain.append(('list_price', '>=', float(min_price)))

        max_price = kw.get('max_price')
        if max_price:
            domain.append(('list_price', '<=', float(max_price)))

        order = kw.get('order', 'name asc')
        Product = request.env['product.template'].sudo()
        total = Product.search_count(domain)
        products = Product.search(domain, limit=limit, offset=offset, order=order)

        # Field selection
        req_fields = None
        if kw.get('fields'):
            req_fields = [f.strip() for f in kw['fields'].split(',')]
            req_fields = [f for f in req_fields if f in PRODUCT_FIELDS]

        records = [_serialize_product(p, req_fields) for p in products]

        return _json_response({
            'success': True,
            'data': records,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit if limit else 1,
            },
        })

    # ----------------------------------------------------- GET /products/<id>
    @http.route('/api/v1/products/<int:product_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth(scopes=['products_read'])
    def get_product(self, product_id, **kw):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return _error_response('Product not found', 404)
        return _json_response({
            'success': True,
            'data': _serialize_product(product),
        })

    # ----------------------------------------------------- POST /products
    @http.route('/api/v1/products', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    @api_auth(scopes=['products_write'])
    def create_product(self, **kw):
        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        required = ['name']
        for field in required:
            if field not in body:
                return _error_response(f'Missing required field: {field}', 400)

        vals = {}
        writable = ['name', 'default_code', 'barcode', 'list_price', 'standard_price',
                     'categ_id', 'type', 'description_sale']
        for key in writable:
            if key in body:
                vals[key] = body[key]

        product = request.env['product.template'].sudo().create(vals)

        return _json_response({
            'success': True,
            'data': _serialize_product(product),
            'message': 'Product created successfully',
        }, status=201)

    # ----------------------------------------------------- PUT /products/<id>
    @http.route('/api/v1/products/<int:product_id>', type='http', auth='none',
                methods=['PUT', 'PATCH'], csrf=False, cors='*')
    @api_auth(scopes=['products_write'])
    def update_product(self, product_id, **kw):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return _error_response('Product not found', 404)

        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        writable = ['name', 'default_code', 'barcode', 'list_price', 'standard_price',
                     'categ_id', 'type', 'description_sale']
        vals = {k: v for k, v in body.items() if k in writable}

        if vals:
            product.write(vals)

        return _json_response({
            'success': True,
            'data': _serialize_product(product),
            'message': 'Product updated successfully',
        })

    # ----------------------------------------------------- DELETE /products/<id>
    @http.route('/api/v1/products/<int:product_id>', type='http', auth='none',
                methods=['DELETE'], csrf=False, cors='*')
    @api_auth(scopes=['products_write'])
    def delete_product(self, product_id, **kw):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return _error_response('Product not found', 404)
        product.write({'active': False})  # soft delete
        return _json_response({
            'success': True,
            'message': 'Product archived successfully',
        })
