from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ahps_kyc_state = fields.Selection(
        related="partner_id.commercial_partner_id.ahps_kyc_state", string="Customer KYC",
    )
    ahps_customer_number = fields.Char(
        related="partner_id.commercial_partner_id.ahps_customer_number", string="Customer ID",
    )

    def action_quotation_send(self):
        self.partner_id._ahps_check_kyc_approved(self.env._("send a quotation"))
        return super().action_quotation_send()

    def action_confirm(self):
        self.partner_id._ahps_check_kyc_approved(self.env._("confirm an order"))
        return super().action_confirm()
