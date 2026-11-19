from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ahps_kyc_required = fields.Boolean(related="company_id.ahps_kyc_required", readonly=False)
    ahps_kyc_form = fields.Binary(related="company_id.ahps_kyc_form", readonly=False)
    ahps_kyc_form_name = fields.Char(related="company_id.ahps_kyc_form_name", readonly=False)
