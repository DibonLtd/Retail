{
    "name": "Tano Retail M-PESA Base",
    "summary": "Safaricom Daraja integration: configuration, transactions and callbacks",
    "version": "18.0.1.0.0",
    "category": "Accounting/Payment",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_base", "account"],
    # Declared so Odoo reports a clear "library not installed" message
    # instead of failing to import the module with a bare traceback.
    "external_dependencies": {"python": ['requests']},
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
