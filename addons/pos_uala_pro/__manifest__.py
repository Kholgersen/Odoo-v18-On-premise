{
    "name": "POS Ualá Pro Integration",
    "version": "1.0",
    "category": "Point of Sale",
    "summary": "Integración de terminal Ualá Pro en POS",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_config_view.xml",
        "views/pos_payment_method_view.xml",
        "security/ir.model.access.csv"
    ],
    "assets": {
        "point_of_sale.assets": [
            "pos_uala_pro/static/src/js/uala_pro_payment.js"
        ]
    },
    "installable": True,
    "application": False
}
