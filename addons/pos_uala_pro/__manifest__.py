{
    "name": "POS Ualá Pro Integration",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Integración de terminal Ualá Pro en POS",
    "depends": ["point_of_sale"],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_config_view.xml',
        'views/pos_payment_method_view.xml',
        'views/res_config_settings_view.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'pos_uala_pro/static/src/js/uala_pro_payment.js',
            'pos_uala_pro/static/src/xml/uala_pro_payment_button.xml',
        ],
    },
    "assets": {
        "point_of_sale.assets": [
            "pos_uala_pro/static/src/js/uala_pro_payment.js"
        ]
    },
    "installable": True,
    "application": False
}
