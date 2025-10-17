{
    'name': 'Real Estate Property Management',
    'version': '1.0',
    'category': 'Real Estate',
    'summary': 'Gestión de propiedades inmobiliarias unificadas (venta y alquiler)',
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale', 'sale_subscription', 'contacts', 'product'
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/menuitems.xml',
        'views/property_views.xml',
    ],
    'application': True,
    'installable': True,
}