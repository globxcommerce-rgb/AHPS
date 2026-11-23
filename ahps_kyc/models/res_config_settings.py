from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ahps_kyc_required = fields.Boolean(related="company_id.ahps_kyc_required", readonly=False)
    ahps_kyc_public_registration = fields.Boolean(related="company_id.ahps_kyc_public_registration", readonly=False)
    ahps_kyc_public_url = fields.Char(compute="_compute_ahps_kyc_public_url")

    @api.depends("company_id")
    def _compute_ahps_kyc_public_url(self):
        for settings in self:
            settings.ahps_kyc_public_url = f"{settings.company_id.get_base_url()}/kyc/register"
