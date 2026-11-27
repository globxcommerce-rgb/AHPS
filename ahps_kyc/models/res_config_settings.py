from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ahps_kyc_required = fields.Boolean(related="company_id.ahps_kyc_required", readonly=False)
    ahps_kyc_public_registration = fields.Boolean(related="company_id.ahps_kyc_public_registration", readonly=False)
    ahps_kyc_public_url = fields.Char(string="Customer Registration Link", compute="_compute_ahps_kyc_public_url")
    ahps_kyc_public_supplier_url = fields.Char(string="Supplier Registration Link", compute="_compute_ahps_kyc_public_url")

    @api.depends("company_id")
    def _compute_ahps_kyc_public_url(self):
        for settings in self:
            base_url = settings.company_id.get_base_url()
            settings.ahps_kyc_public_url = f"{base_url}/kyc/register/customer"
            settings.ahps_kyc_public_supplier_url = f"{base_url}/kyc/register/supplier"
