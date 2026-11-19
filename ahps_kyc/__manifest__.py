{
    "name": "aHPS Customer KYC",
    "version": "20.0.1.0.0",
    "summary": "KYC registration, review and approval of aHPS customers",
    "description": """
Customer KYC process for Advanced Helios Process Solutions Ltd (aHPS):

* KYC tab on companies: TIN, company registration, postal address, company group,
  customer type (End User / Reseller) and end-user subcategory
* Main, alternative, procurement and finance contacts
* KYC documents (signed KYC form, certificates, ...)
* KYC workflow: Not Started > Requested > Submitted > Approved / Rejected
* Customer number in YYYY.NNN format, assigned on approval
* Duplicate company warning (same name or TIN)
* Quotations cannot be sent or confirmed, and invoices cannot be posted,
  for customers whose KYC is not approved (configurable)
""",
    "author": "Globx",
    "website": "https://www.globx.group",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "depends": ["contacts", "sale_management", "account", "mail"],
    "data": [
        "security/ahps_kyc_security.xml",
        "security/ir.access.csv",
        "data/ir_sequence_data.xml",
        "data/ahps_kyc_document_type_data.xml",
        "data/mail_template_data.xml",
        "wizard/ahps_kyc_reject_wizard_views.xml",
        "views/ahps_kyc_document_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/ahps_kyc_menus.xml",
    ],
    "installable": True,
    "application": False,
}
