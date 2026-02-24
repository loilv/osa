{
    'name': 'Livechat Session Sidebar + Zalo Integration',
    'version': '2.0',
    'summary': 'Livechat sidebar with Zalo multi-account integration via zca-js bridge',
    'category': 'Website/Live Chat',
    'depends': ['im_livechat'],
    'data': [
        'security/ir.model.access.csv',
        'views/zalo_account_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'livechat_sidebar/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
