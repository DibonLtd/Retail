{
    "name": "Tano Retail POS",
    "summary": "Out-of-stock guard, VAT receipt details and return window for the tills",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_base", "point_of_sale", "stock"],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "retail_pos/static/src/js/pos_store_stock_guard.js",
        ],
    },
    "installable": True,
    "application": False,
}
