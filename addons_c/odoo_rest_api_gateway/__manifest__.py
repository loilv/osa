# -*- coding: utf-8 -*-
{
    'name': 'REST API Gateway Pro',
    'version': '19.0.1.0.0',
    'category': 'Technical/API',
    'summary': 'Production-ready REST API with JWT Auth, Rate Limiting, Swagger & Analytics Dashboard',
    'description': """
        🚀 REST API Gateway Pro - Odoo 19
        ===================================

        Turn Odoo into a headless, secure, mobile-ready REST API server.

        🔥 Key Features:
        ----------------
        ✅ JWT Authentication (login + refresh tokens)
        ✅ API Key Management (per-app keys with scopes)
        ✅ RESTful Endpoints for Products, Orders, Customers
        ✅ Rate Limiting Engine (per-minute / per-hour)
        ✅ IP Whitelisting & Company Isolation
        ✅ Swagger / OpenAPI Documentation (/api/docs)
        ✅ API Usage Analytics Dashboard (OWL)
        ✅ Request Logging & Audit Trail
        ✅ Pagination, Search, Field Selection
        ✅ Cron-based log cleanup & rate-limit reset

        💡 Perfect for:
        - Mobile app backends (Flutter / React Native)
        - Headless e-commerce (React / Next.js)
        - SaaS API providers
        - Third-party integrations
        - Marketplace connectors

        🛠️ Technical:
        - PyJWT-based token signing
        - Middleware-level security checks
        - OWL 2 dashboard components
        - Auto-generated Swagger docs
    """,
    'author': 'Aura Odoo Tech',
    'website': 'http://auraodoo.tech/',
    'license': 'LGPL-3',
   
    'depends': [
        'base',
        'web',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/api_key_views.xml',
        'views/api_log_views.xml',
        'views/api_scope_views.xml',
        'views/dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_rest_api_gateway/static/src/scss/dashboard.scss',
            'odoo_rest_api_gateway/static/src/js/dashboard/api_dashboard.js',
            'odoo_rest_api_gateway/static/src/js/dashboard/api_dashboard.xml',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'external_dependencies': {
        'python': ['PyJWT'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
