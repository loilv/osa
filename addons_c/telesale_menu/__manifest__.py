{
    'name': 'Telesale Menu',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Grid home menu for Odoo backend - Telesale project',
    'description': """
        This module provides a grid-style home menu for Odoo backend.
        Features:
        - Grid app launcher with icons
        - Search/filter apps
        - Smooth animations
        - Modern design
        - Custom logo and favicon settings
    """,
    'author': 'Custom',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['web', 'base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'telesale_menu/static/src/scss/telesale_menu.scss',
            'telesale_menu/static/src/js/telesale_menu.js',
            'telesale_menu/static/src/xml/telesale_menu.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
