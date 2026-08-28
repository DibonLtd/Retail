{
    "name": "Tano Retail POS Sales Report",
    "summary": "Daily and per-item POS sales summary with payment reconciliation",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_base", "point_of_sale"],
    # Declared so Odoo reports a clear "library not installed" message
    # instead of failing to import the module with a bare traceback.
    "external_dependencies": {"python": ['xlsxwriter']},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/pos_sales_report_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
