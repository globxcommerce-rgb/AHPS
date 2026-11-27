{
    "name": "aHPS KYC (Customers & Suppliers)",
    "version": "20.0.1.2.0",
    "summary": "KYC registration, review and approval of aHPS customers and suppliers",
    "description": """
Customer and supplier KYC process for Advanced Helios Process Solutions Ltd (aHPS):

* Separate online KYC forms for customers and suppliers (link sent by email, form
  fixed by "Registers As"; optional public pages /kyc/register/customer|supplier): company details, contact persons, invoice / delivery
  addresses, documents, bank details (suppliers) and declaration
* KYC tab on companies: TIN, company registration, postal address, company group,
  customer category as contact tags (End User > sector, Reseller)
* Main, authorized, alternative, procurement and finance contacts
* KYC documents per registration type (certificates, tax compliance, business
  license, bank letter, audited accounts for suppliers)
* KYC workflow: Not Started > Requested > Submitted > Approved / Rejected
* Customer ID (CYYYY.NNN) and supplier ID (SYYYY.NNN), assigned on approval
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
