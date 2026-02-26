# -*- coding: utf-8 -*-
{
    'name': 'Asterisk Connector',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'Tích hợp Odoo với Asterisk PBX - Quay số, nhận cuộc gọi, chuyển cuộc gọi',
    'description': """
Asterisk Connector for Odoo
===========================
Module tích hợp Odoo với hệ thống tổng đài Asterisk PBX.

Tính năng:
----------
* Quay số trực tiếp từ Odoo (Click-to-call)
* Nhận cuộc gọi với popup thông báo
* Chuyển cuộc gọi (Transfer)
* Hiển thị thông tin khách hàng khi có cuộc gọi đến
* Lịch sử cuộc gọi
* Âm báo khi có cuộc gọi đến
    """,
    'author': 'Odoo Community',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'mail',
        'web',
    ],
    'data': [
        'security/asterisk_security.xml',
        'security/ir.model.access.csv',
        'views/asterisk_user_views.xml',
        'views/call_log_views.xml',
        'views/asterisk_server_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'asterisk_connector/static/lib/sip.js',
            'asterisk_connector/static/src/scss/phone_widget.scss',
            'asterisk_connector/static/src/js/phone_service.js',
            'asterisk_connector/static/src/js/phone_widget.js',
            'asterisk_connector/static/src/js/systray_phone.js',
            'asterisk_connector/static/src/js/asterisk_phone_field.js',
            'asterisk_connector/static/src/xml/phone_templates.xml',
            'asterisk_connector/static/src/xml/asterisk_phone_field.xml',
        ],
    },
    'external_dependencies': {
        'python': ['asterisk-ami'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
