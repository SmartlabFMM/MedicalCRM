{
    'name': 'IoT Patient Monitoring',
    'version': '1.0',
    'summary': 'Medical IoT Monitoring System',
    'author': 'Ines Aouida',
    'category': 'Healthcare',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/patient_views.xml',
    ],
    'installable': True,
    'application': True,
}