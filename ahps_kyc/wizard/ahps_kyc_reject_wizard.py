from odoo import fields, models


class AhpsKycRejectWizard(models.TransientModel):
    _name = "ahps.kyc.reject.wizard"
    _description = "Reject KYC"

    partner_ids = fields.Many2many("res.partner", string="Customers", required=True)
    reason = fields.Text(required=True)
    notify_customer = fields.Boolean(
        string="Email the reason to the company", default=True,
        help="Send the reason and the link to the online KYC form, so the company can correct and resubmit.")

    def action_reject(self):
        self.partner_ids._ahps_kyc_do_reject(self.reason, notify=self.notify_customer)
        return {"type": "ir.actions.act_window_close"}
