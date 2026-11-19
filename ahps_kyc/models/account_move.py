from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        for move in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
            move.partner_id._ahps_check_kyc_approved(self.env._("post an invoice"))
        return super()._post(soft=soft)
