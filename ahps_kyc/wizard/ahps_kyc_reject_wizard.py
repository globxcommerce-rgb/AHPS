from odoo import fields, models


class AhpsKycRejectWizard(models.TransientModel):
    _name = "ahps.kyc.reject.wizard"
    _description = "Reject Customer KYC"

    partner_ids = fields.Many2many("res.partner", string="Customers", required=True)
    reason = fields.Text(required=True)

    def action_reject(self):
        self.partner_ids._ahps_kyc_do_reject(self.reason)
        return {"type": "ir.actions.act_window_close"}
