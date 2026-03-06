# -*- coding: utf-8 -*-
"""
Swagger / OpenAPI documentation controller.
Serves a self-contained Swagger UI page at /api/docs and the OpenAPI spec at /api/v1/spec.
"""

import json
import logging

from odoo import http
from odoo.http import request

from .api_middleware import _json_response

_logger = logging.getLogger(__name__)


OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Odoo REST API Gateway Pro",
        "version": "1.0.0",
        "description": "Production-ready REST API for Odoo 19 – JWT Auth, API Keys, Rate Limiting.",
        "contact": {"name": "Aura Odoo Tech", "url": "http://auraodoo.tech/"},
    },
    "servers": [{"url": "/api/v1", "description": "API v1"}],
    "components": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            },
        },
        "schemas": {
            "LoginRequest": {
                "type": "object",
                "required": ["email", "password"],
                "properties": {
                    "email": {"type": "string", "example": "admin@example.com"},
                    "password": {"type": "string", "example": "admin"},
                },
            },
            "TokenResponse": {
                "type": "object",
                "properties": {
                    "access_token": {"type": "string"},
                    "refresh_token": {"type": "string"},
                    "expires_in": {"type": "integer", "example": 3600},
                    "token_type": {"type": "string", "example": "Bearer"},
                },
            },
            "Product": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "default_code": {"type": "string"},
                    "list_price": {"type": "number"},
                    "categ_id": {"type": "object"},
                },
            },
            "OrderLine": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "quantity": {"type": "number", "default": 1},
                    "price_unit": {"type": "number"},
                    "discount": {"type": "number", "default": 0},
                },
            },
            "CreateOrder": {
                "type": "object",
                "required": ["partner_id", "order_lines"],
                "properties": {
                    "partner_id": {"type": "integer"},
                    "order_lines": {"type": "array", "items": {"$ref": "#/components/schemas/OrderLine"}},
                    "auto_confirm": {"type": "boolean", "default": False},
                    "note": {"type": "string"},
                },
            },
            "Customer": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                },
            },
            "PaginatedResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": "array", "items": {}},
                    "pagination": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer"},
                            "limit": {"type": "integer"},
                            "total": {"type": "integer"},
                            "pages": {"type": "integer"},
                        },
                    },
                },
            },
            "Error": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": False},
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    "paths": {
        "/auth/login": {
            "post": {
                "tags": ["Authentication"],
                "summary": "Login – get JWT tokens",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LoginRequest"}
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Tokens returned",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenResponse"}}},
                    },
                    "401": {"description": "Invalid credentials"},
                },
            }
        },
        "/auth/refresh": {
            "post": {
                "tags": ["Authentication"],
                "summary": "Refresh access token",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"refresh_token": {"type": "string"}},
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "New tokens"}},
            }
        },
        "/auth/me": {
            "get": {
                "tags": ["Authentication"],
                "summary": "Get current user info",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "responses": {"200": {"description": "User profile"}},
            }
        },
        "/products": {
            "get": {
                "tags": ["Products"],
                "summary": "List products",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}},
                    {"name": "search", "in": "query", "schema": {"type": "string"}},
                    {"name": "category", "in": "query", "schema": {"type": "integer"}},
                    {"name": "min_price", "in": "query", "schema": {"type": "number"}},
                    {"name": "max_price", "in": "query", "schema": {"type": "number"}},
                    {"name": "fields", "in": "query", "schema": {"type": "string"}},
                    {"name": "order", "in": "query", "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Paginated product list"},
                },
            },
            "post": {
                "tags": ["Products"],
                "summary": "Create a product",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Product"}}},
                },
                "responses": {"201": {"description": "Product created"}},
            },
        },
        "/products/{id}": {
            "get": {
                "tags": ["Products"],
                "summary": "Get a single product",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Product detail"}},
            },
            "put": {
                "tags": ["Products"],
                "summary": "Update a product",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Product updated"}},
            },
            "delete": {
                "tags": ["Products"],
                "summary": "Archive a product",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Product archived"}},
            },
        },
        "/orders": {
            "get": {
                "tags": ["Orders"],
                "summary": "List sale orders",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    {"name": "state", "in": "query", "schema": {"type": "string"}},
                    {"name": "partner_id", "in": "query", "schema": {"type": "integer"}},
                    {"name": "date_from", "in": "query", "schema": {"type": "string", "format": "date"}},
                    {"name": "date_to", "in": "query", "schema": {"type": "string", "format": "date"}},
                ],
                "responses": {"200": {"description": "Paginated order list"}},
            },
            "post": {
                "tags": ["Orders"],
                "summary": "Create a sale order",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CreateOrder"}}},
                },
                "responses": {"201": {"description": "Order created"}},
            },
        },
        "/orders/{id}": {
            "get": {
                "tags": ["Orders"],
                "summary": "Get a single order",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Order detail"}},
            },
        },
        "/orders/{id}/confirm": {
            "post": {
                "tags": ["Orders"],
                "summary": "Confirm a draft order",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Order confirmed"}},
            },
        },
        "/orders/{id}/cancel": {
            "post": {
                "tags": ["Orders"],
                "summary": "Cancel an order",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Order cancelled"}},
            },
        },
        "/customers": {
            "get": {
                "tags": ["Customers"],
                "summary": "List customers",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    {"name": "search", "in": "query", "schema": {"type": "string"}},
                    {"name": "is_company", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "country_id", "in": "query", "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "Paginated customer list"}},
            },
            "post": {
                "tags": ["Customers"],
                "summary": "Create a customer",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Customer"}}},
                },
                "responses": {"201": {"description": "Customer created"}},
            },
        },
        "/customers/{id}": {
            "get": {
                "tags": ["Customers"],
                "summary": "Get a single customer",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Customer detail"}},
            },
            "put": {
                "tags": ["Customers"],
                "summary": "Update a customer",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Customer updated"}},
            },
            "delete": {
                "tags": ["Customers"],
                "summary": "Archive a customer",
                "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Customer archived"}},
            },
        },
    },
}


class SwaggerController(http.Controller):

    @http.route('/api/v1/spec', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def openapi_spec(self, **kw):
        """Return the OpenAPI 3.0 JSON spec."""
        return _json_response(OPENAPI_SPEC)

    @http.route('/api/docs', type='http', auth='none', methods=['GET'], csrf=False)
    def swagger_ui(self, **kw):
        """Serve a self-contained Swagger UI page (CDN-based)."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Odoo REST API – Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
    <style>
        body { margin: 0; background: #fafafa; }
        .topbar { display: none !important; }
        .swagger-ui .info hgroup.main h2 { display: none; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({
            url: '/api/v1/spec',
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
            layout: 'BaseLayout',
        });
    </script>
</body>
</html>"""
        return request.make_response(html, headers=[('Content-Type', 'text/html')])
