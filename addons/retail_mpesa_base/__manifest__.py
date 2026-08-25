{
    "name": "Tano Retail M-PESA Base",
    "summary": "Safaricom Daraja integration: configuration, transactions and callbacks",
    "version": "18.0.1.0.0",
    "category": "Accounting/Payment",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "security/mpesa_rules.xml",
        "views/mpesa_config_views.xml",
        "views/mpesa_transaction_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
