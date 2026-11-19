from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ahps_kyc_required = fields.Boolean(
        string="Require Approved KYC",
        default=True,
        help="Block sending/confirming quotations and posting customer invoices "
        "for customers whose KYC is not approved.",
    )
    ahps_kyc_form = fields.Binary(string="Blank KYC Form", attachment=True)
    ahps_kyc_form_name = fields.Char(string="KYC Form File Name")

    def write(self, vals):
        res = super().write(vals)
        if "ahps_kyc_form" in vals or "ahps_kyc_form_name" in vals:
            self._ahps_sync_kyc_form_attachment()
        return res

    def _ahps_sync_kyc_form_attachment(self):
        """Attach the blank KYC form to the KYC request email template."""
        template = self.env.ref("ahps_kyc.mail_template_ahps_kyc_request", raise_if_not_found=False)
        if not template:
            return
        template = template.sudo()
        old = template.attachment_ids.filtered(lambda a: a.description == "ahps_kyc_form")
        template.attachment_ids = [(3, a.id) for a in old]
        old.unlink()
        company = self[:1]
        if company.ahps_kyc_form:
            attachment = self.env["ir.attachment"].sudo().create({
                "name": company.ahps_kyc_form_name or "KYC Form.pdf",
                "raw": company.ahps_kyc_form.content,
                "res_model": "mail.template",
                "res_id": template.id,
                "description": "ahps_kyc_form",
            })
            template.attachment_ids = [(4, attachment.id)]
