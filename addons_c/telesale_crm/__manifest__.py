{
    'name': 'Telesale CRM',
    'version': '19.0.1.0.0',
    'category': 'Telesale/Backend',
    'summary': 'TELESALE CRM',
    'description': """
    """,
    'author': 'Custom',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['web', 'crm', 'asterisk_connector'],
    'data': [
        'security/ir.model.access.csv',
        'views/crm_lead.xml',
        'views/action_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
