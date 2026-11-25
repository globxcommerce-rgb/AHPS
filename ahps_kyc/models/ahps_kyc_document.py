import base64

from odoo import api, fields, models


class AhpsKycDocumentType(models.Model):
    _name = "ahps.kyc.document.type"
    _description = "KYC Document Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(
        string="Required",
        help="A document of this type must be attached before the KYC can be submitted.",
    )
    applies_to = fields.Selection(
        [("customer", "Customers"), ("supplier", "Suppliers"), ("both", "Customers and Suppliers")],
        string="Asked From", required=True, default="both",
        help="Which registrations ask for this document on the online KYC form.",
    )
    portal_visible = fields.Boolean(string="On Online Form", default=True,
                                    help="Ask for this document on the online KYC form.")
    description = fields.Char(help="Short hint shown on the online form.")
    active = fields.Boolean(default=True)

    @api.model
    def _ahps_types_for(self, registration_type):
        return self.search([("applies_to", "in", (registration_type or "customer", "both"))])

    @api.model
    def _ahps_required_types(self, registration_type):
        return self._ahps_types_for(registration_type).filtered("required")


class AhpsKycDocument(models.Model):
    _name = "ahps.kyc.document"
    _description = "KYC Document"
    _order = "partner_id, document_type_id, id"

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, index=True, ondelete="cascade",
        domain="[('parent_id', '=', False)]",
    )
    document_type_id = fields.Many2one("ahps.kyc.document.type", string="Document Type", required=True)
    name = fields.Char(string="Description")
    attachment = fields.Binary(string="File", attachment=True, required=True)
    attachment_name = fields.Char(string="File Name")
    issue_date = fields.Date()
    expiry_date = fields.Date()
    is_expired = fields.Boolean(compute="_compute_is_expired")
    note = fields.Char()
    partner_attachment_id = fields.Many2one(
        "ir.attachment", string="File on Contact", readonly=True, copy=False, ondelete="set null",
        help="Copy of the file attached to the company, so it can be viewed from the Files of the chatter.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        docs = super().create(vals_list)
        docs._ahps_attach_to_partner()
        return docs

    def write(self, vals):
        res = super().write(vals)
        if {"attachment", "attachment_name", "partner_id", "document_type_id"} & set(vals):
            self._ahps_attach_to_partner()
        return res

    def _ahps_file_content(self):
        self.ensure_one()
        value = self.with_context(bin_size=False).attachment
        if not value:
            return b""
        content = getattr(value, "content", None)
        if content is not None:
            return content
        return base64.b64decode(value) if isinstance(value, (str, bytes)) else b""

    def _ahps_attach_to_partner(self, post=None):
        """Attach each document's file to its company, where it shows in the Files of the chatter and
        opens in the viewer. Earlier versions stay attached (history of what was submitted)."""
        if post is None:
            post = not self.env.context.get("ahps_kyc_no_post")
        Attachment = self.env["ir.attachment"].sudo()
        new_by_partner = {}
        for doc in self.sudo():
            content = doc._ahps_file_content()
            if not content or not doc.partner_id:
                continue
            filename = doc.attachment_name or "document"
            attachment = Attachment.create({
                "name": f"{doc.document_type_id.name} - {filename}",
                "raw": content,
                "res_model": "res.partner",
                "res_id": doc.partner_id.id,
            })
            super(AhpsKycDocument, doc).write({"partner_attachment_id": attachment.id})
            new_by_partner.setdefault(doc.partner_id, Attachment)
            new_by_partner[doc.partner_id] |= attachment
        if post:
            for partner, attachments in new_by_partner.items():
                partner.message_post(
                    body=self.env._("KYC documents added: %s", ", ".join(attachments.mapped("name"))),
                    attachment_ids=attachments.ids,
                )
        return new_by_partner

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.is_expired = bool(doc.expiry_date and doc.expiry_date < today)
