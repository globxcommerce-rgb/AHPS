from odoo import api, fields, models


class AhpsKycDocumentType(models.Model):
    _name = "ahps.kyc.document.type"
    _description = "KYC Document Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(
        string="Required for KYC",
        help="A document of this type must be attached before the KYC can be submitted.",
    )
    active = fields.Boolean(default=True)


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

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.is_expired = bool(doc.expiry_date and doc.expiry_date < today)
