{
    "name": "aHPS KYC (Customers & Suppliers)",
    "version": "20.0.1.1.0",
    "summary": "KYC registration, review and approval of aHPS customers and suppliers",
    "description": """
Customer and supplier KYC process for Advanced Helios Process Solutions Ltd (aHPS):

* Online KYC form (link sent by email, or optional public registration page) for
  customers and suppliers: company details, contact persons, invoice / delivery
  addresses, documents, bank details (suppliers) and declaration
* KYC tab on companies: TIN, company registration, postal address, company group,
  customer category as contact tags (End User > sector, Reseller)
* Main, authorized, alternative, procurement and finance contacts
* KYC documents per registration type (certificates, tax compliance, business
  license, bank letter for suppliers)
* KYC workflow: Not Started > Requested > Submitted > Approved / Rejected
* Customer number in YYYY.NNN format, assigned on approval of a customer;
  approved suppliers are flagged as vendors
* Duplicate company warning (same name or TIN)
* Quotations cannot be sent or confirmed, and invoices cannot be posted,
  for customers whose KYC is not approved (configurable)
""",
    "author": "Globx",
    "website": "https://www.globx.group",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "depends": ["contacts", "sale_management", "account", "mail", "portal"],
    "data": [
        "security/ahps_kyc_security.xml",
        "security/ir.access.csv",
        "data/ir_sequence_data.xml",
        "data/res_partner_category_data.xml",
        "data/ahps_kyc_document_type_data.xml",
        "data/mail_template_data.xml",
        "wizard/ahps_kyc_reject_wizard_views.xml",
        "views/ahps_kyc_document_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/ahps_kyc_menus.xml",
        "views/portal_kyc_templates.xml",
    ],
    "installable": True,
    "application": False,
}
