{
    "name": "Tano Retail Kenyan Fiscal",
    "summary": "Kenyan VAT classification and ESD fiscal printing for the tills",
    "description": """
Kenyan fiscal support for Tano Retail.

Carries forward the tax classification model from the Odoo 17 Novitus ESD
module: each tax holds a PTU letter and a factor type (taxable, exempted or
zero rated), and a product inherits its classification from its single tax.
That is the correct model for a Kenyan supermarket basket, where maize flour
and milk are not standard rated.

Fiscal transmissions are recorded in fiscal.log, and the device transport is
isolated behind fiscal.printer._send so it can be exercised without hardware.
""",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "license": "LGPL-3",
    "author": "Dibon",
    "depends": ["retail_base", "point_of_sale", "l10n_ke"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_tax_views.xml",
        "views/product_template_views.xml",
        "views/fiscal_printer_views.xml",
        "views/fiscal_log_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
