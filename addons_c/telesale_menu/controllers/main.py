# -*- coding: utf-8 -*-

import base64
import hashlib
from odoo import http
from odoo.http import request


class TelesaleMenuController(http.Controller):

    @http.route('/telesale_menu/logo', type='http', auth='user')
    def get_telesale_logo(self):
        """Return the logo for the current company."""
        company = request.env.company
        if company.telesale_logo:
            image_data = base64.b64decode(company.telesale_logo)
            # Detect image type
            content_type = 'image/png'
            if image_data[:3] == b'\xff\xd8\xff':
                content_type = 'image/jpeg'
            elif image_data[:4] == b'\x89PNG':
                content_type = 'image/png'
            elif image_data[:6] in (b'GIF87a', b'GIF89a'):
                content_type = 'image/gif'
            
            return request.make_response(
                image_data,
                headers=[
                    ('Content-Type', content_type),
                    ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                    ('Pragma', 'no-cache'),
                    ('Expires', '0'),
                ]
            )
        # Fallback to default Odoo logo
        return request.redirect('/web/static/img/logo.png')

    @http.route('/telesale_menu/favicon', type='http', auth='public')
    def get_favicon(self):
        """Return the favicon for the current company."""
        try:
            company = request.env.company
        except Exception:
            company = None
        
        if company and company.telesale_favicon:
            image_data = base64.b64decode(company.telesale_favicon)
            # Detect content type
            content_type = 'image/x-icon'
            if image_data[:4] == b'\x89PNG':
                content_type = 'image/png'
            elif image_data[:3] == b'\xff\xd8\xff':
                content_type = 'image/jpeg'
            
            return request.make_response(
                image_data,
                headers=[
                    ('Content-Type', content_type),
                    ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                    ('Pragma', 'no-cache'),
                    ('Expires', '0'),
                ]
            )
        # Fallback to default favicon
        return request.redirect('/web/static/img/favicon.ico')
