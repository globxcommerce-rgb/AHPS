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

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.is_expired = bool(doc.expiry_date and doc.expiry_date < today)
