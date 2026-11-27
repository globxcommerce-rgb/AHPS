from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ahps_kyc_required = fields.Boolean(
        string="Require Approved KYC",
        default=True,
        help="Block sending/confirming quotations and posting customer invoices "
        "for customers whose KYC is not approved.",
    )
    ahps_kyc_public_registration = fields.Boolean(
        string="Public Registration Page",
        help="Allow new customers and suppliers to register themselves at /kyc/register/customer "
        "or /kyc/register/supplier "
        "(for example from a link on the aHPS website or email signature).",
    )
