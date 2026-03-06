# -*- coding: utf-8 -*-
"""
Sales Order API – create, list, and manage orders from external apps.
"""

import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

from .api_middleware import api_auth, _json_response, _error_response

_logger = logging.getLogger(__name__)


def _serialize_order(order):
    """Convert a sale.order to a JSON-safe dict."""
    lines = []
    for line in order.order_line:
        lines.append({
            'id': line.id,
            'product_id': line.product_id.id,
            'product_name': line.product_id.display_name,
            'product_uom_qty': line.product_uom_qty,
            'price_unit': line.price_unit,
            'discount': line.discount,
            'price_subtotal': line.price_subtotal,
            'price_total': line.price_total,
        })
    return {
        'id': order.id,
        'name': order.name,
        'state': order.state,
        'partner_id': order.partner_id.id,
        'partner_name': order.partner_id.display_name,
        'date_order': str(order.date_order) if order.date_order else None,
        'amount_untaxed': order.amount_untaxed,
        'amount_tax': order.amount_tax,
        'amount_total': order.amount_total,
        'currency': order.currency_id.name,
        'company_id': order.company_id.id,
        'order_lines': lines,
    }


class OrderController(http.Controller):

    # ------------------------------------------------ GET /orders
    @http.route('/api/v1/orders', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth(scopes=['orders_read'])
    def list_orders(self, **kw):
        page = int(kw.get('page', 1))
        limit = min(int(kw.get('limit', 20)), 100)
        offset = (page - 1) * limit

        domain = []
        state = kw.get('state')
        if state:
            domain.append(('state', '=', state))

        partner_id = kw.get('partner_id')
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))

        date_from = kw.get('date_from')
        if date_from:
            domain.append(('date_order', '>=', date_from))

        date_to = kw.get('date_to')
        if date_to:
            domain.append(('date_order', '<=', date_to))

        order_by = kw.get('order', 'date_order desc')

        Order = request.env['sale.order'].sudo()
        total = Order.search_count(domain)
        orders = Order.search(domain, limit=limit, offset=offset, order=order_by)

        return _json_response({
            'success': True,
            'data': [_serialize_order(o) for o in orders],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit if limit else 1,
            },
        })

    # ------------------------------------------------ GET /orders/<id>
    @http.route('/api/v1/orders/<int:order_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_auth(scopes=['orders_read'])
    def get_order(self, order_id, **kw):
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return _error_response('Order not found', 404)
        return _json_response({
            'success': True,
            'data': _serialize_order(order),
        })

    # ------------------------------------------------ POST /orders
    @http.route('/api/v1/orders', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    @api_auth(scopes=['orders_write'])
    def create_order(self, **kw):
        try:
            body = json.loads(request.httprequest.data or '{}')
        except Exception:
            return _error_response('Invalid JSON body', 400)

        partner_id = body.get('partner_id')
        if not partner_id:
            return _error_response('partner_id is required', 400)

        partner = request.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists():
            return _error_response('Partner not found', 404)

        lines_data = body.get('order_lines', [])
        if not lines_data:
            return _error_response('At least one order_line is required', 400)

        order_vals = {
            'partner_id': partner.id,
            'order_line': [],
        }

        if body.get('date_order'):
            order_vals['date_order'] = body['date_order']

        if body.get('note'):
            order_vals['note'] = body['note']

        for line in lines_data:
            product_id = line.get('product_id')
            if not product_id:
                return _error_response('Each order_line must have a product_id', 400)

            product = request.env['product.product'].sudo().browse(int(product_id))
            if not product.exists():
                return _error_response(f'Product {product_id} not found', 404)

            line_vals = {
                'product_id': product.id,
                'product_uom_qty': float(line.get('quantity', 1)),
            }
            if 'price_unit' in line:
                line_vals['price_unit'] = float(line['price_unit'])
            if 'discount' in line:
                line_vals['discount'] = float(line['discount'])

            order_vals['order_line'].append((0, 0, line_vals))

        order = request.env['sale.order'].sudo().create(order_vals)

        # Auto-confirm if requested
        if body.get('auto_confirm'):
            order.action_confirm()

        return _json_response({
            'success': True,
            'data': _serialize_order(order),
            'message': 'Order created successfully',
        }, status=201)

    # ------------------------------------------------ POST /orders/<id>/confirm
    @http.route('/api/v1/orders/<int:order_id>/confirm', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    @api_auth(scopes=['orders_write'])
    def confirm_order(self, order_id, **kw):
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return _error_response('Order not found', 404)
        if order.state != 'draft':
            return _error_response(f'Order is in state "{order.state}", cannot confirm', 400)
        order.action_confirm()
        return _json_response({
            'success': True,
            'data': _serialize_order(order),
            'message': 'Order confirmed',
        })

    # ------------------------------------------------ POST /orders/<id>/cancel
    @http.route('/api/v1/orders/<int:order_id>/cancel', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    @api_auth(scopes=['orders_write'])
    def cancel_order(self, order_id, **kw):
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return _error_response('Order not found', 404)
        order._action_cancel()
        return _json_response({
            'success': True,
            'data': _serialize_order(order),
            'message': 'Order cancelled',
        })
