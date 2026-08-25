{
    "name": "Tano Retail M-PESA at the Till",
    "summary": "Lipa na M-PESA payment method for the point of sale",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_mpesa_base", "point_of_sale"],
    "data": [
        "views/pos_payment_method_views.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "retail_mpesa_pos/static/src/js/mpesa_payment_popup.js",
            "retail_mpesa_pos/static/src/xml/mpesa_payment_popup.xml",
            "retail_mpesa_pos/static/src/js/payment_screen_mpesa.js",
            "retail_mpesa_pos/static/src/js/pos_payment_receipt.js",
        ],
    },
    "installable": True,
    "application": False,
}
