{
    "name": "aHPS Document Templates",
    "version": "20.0.1.0.0",
    "summary": "aHPS layouts for Quotation, Pro Forma Invoice, Invoice, RFQ and Purchase Order",
    "description": """
Prints the aHPS business documents in the client's own formats:

* Quotation (instruments, spare parts and service)
* Pro Forma Invoice (own PFI number, assigned on first print)
* Customer Invoice / Credit Note
* Request for Quotation
* Purchase Order

Adds the fields these documents need (lead time, ports, packing details, gross
weight, HS code, country of origin, charge type, end user on RFQs) and an
"aHPS Documents" tab on the company to manage the texts and logos printed.
""",
    "author": "Globx",
    "website": "https://www.globx.group",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "depends": ["ahps_kyc", "sale_management", "purchase", "account"],
    "data": [
        "data/ir_sequence_data.xml",
        "report/ahps_paperformat.xml",
        "report/ahps_report_common.xml",
        "report/ahps_sale_templates.xml",
        "report/ahps_invoice_templates.xml",
        "report/ahps_purchase_templates.xml",
        "views/res_company_views.xml",
        "views/product_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
