import re
import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

KYC_STATES = [
    ("not_started", "Not Started"),
    ("requested", "KYC Requested"),
    ("submitted", "Submitted for Review"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]

REGISTRATION_TYPES = [
    ("customer", "Customer"),
    ("supplier", "Supplier"),
]

CUSTOMER_NUMBER_RE = re.compile(r"^\d{4}\.\d{3,}$")


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ---- KYC status -------------------------------------------------------
    ahps_kyc_state = fields.Selection(
        KYC_STATES, string="KYC Status", default="not_started", required=True,
        copy=False, tracking=True, index=True,
    )
    ahps_kyc_requested_date = fields.Datetime(string="KYC Requested On", copy=False, readonly=True)
    ahps_kyc_submitted_date = fields.Datetime(string="KYC Submitted On", copy=False, readonly=True)
    ahps_kyc_approved_date = fields.Datetime(string="KYC Approved On", copy=False, readonly=True)
    ahps_kyc_approved_by_id = fields.Many2one("res.users", string="KYC Approved By", copy=False, readonly=True)
    ahps_kyc_rejection_reason = fields.Text(string="Rejection Reason", copy=False, readonly=True)
    ahps_kyc_commercial_state = fields.Selection(
        KYC_STATES, string="Company KYC Status", compute="_compute_ahps_kyc_commercial_state",
        help="KYC status of the company this contact belongs to.",
    )

    # ---- Customer identification -----------------------------------------
    ahps_customer_number = fields.Char(
        string="Customer ID", copy=False, tracking=True, index=True,
        help="aHPS customer number: year of registration and running number, e.g. 2026.021. "
        "Assigned automatically when the KYC is approved.",
    )
    ahps_supplier_number = fields.Char(
        string="Supplier ID", copy=False, tracking=True, index=True,
        help="aHPS supplier number: year of registration and running number, e.g. 2026.066. "
        "Assigned automatically when the KYC of a supplier is approved.",
    )
    ahps_registration_date = fields.Date(
        string="Customer Since", copy=False, tracking=True,
        help="Date the customer was registered with aHPS. Its year is used in the customer number.",
    )
    ahps_company_registry = fields.Char(string="Company Registration No.", tracking=True)
    ahps_postal_address = fields.Char(string="Postal Address", help="e.g. P.O. Box 1325 - 00621")
    ahps_company_group_id = fields.Many2one(
        "res.partner", string="Company Group",
        domain="[('parent_id', '=', False), ('id', '!=', id)]",
        help="International group or conglomerate the customer belongs to.",
    )
    ahps_group_member_ids = fields.One2many("res.partner", "ahps_company_group_id", string="Group Companies")

    # ---- Registration -----------------------------------------------------
    ahps_registration_type = fields.Selection(
        REGISTRATION_TYPES, string="Registers As", default="customer", tracking=True,
        help="Customers get a customer ID on approval; suppliers are registered for purchasing.",
    )
    ahps_company_group_name = fields.Char(
        string="Company Group (declared)",
        help="Group or conglomerate as declared by the customer on the KYC form.",
    )
    ahps_kyc_token = fields.Char(string="KYC Form Token", copy=False, groups="base.group_user")
    ahps_kyc_url = fields.Char(string="Online KYC Form", compute="_compute_ahps_kyc_url")
    ahps_kyc_submitted_online = fields.Boolean(string="Submitted Online", copy=False, readonly=True)
    ahps_kyc_declared_by = fields.Char(string="Declared By", copy=False, readonly=True)
    ahps_kyc_declared_position = fields.Char(string="Declarant Position", copy=False, readonly=True)
    ahps_kyc_declaration_date = fields.Datetime(string="Declaration Date", copy=False, readonly=True)
    ahps_category_tag_ids = fields.Many2many(
        "res.partner.category", string="Customer Category", compute="_compute_ahps_category_tag_ids",
        help="aHPS customer category tags (End User and its sectors, Reseller).",
    )

    # ---- KYC contacts -----------------------------------------------------
    ahps_authorized_contact_id = fields.Many2one(
        "res.partner", string="Authorized Person",
        domain="[('parent_id', '=', id)]",
        help="Person authorised to commit the company (sign orders / contracts).",
    )
    ahps_main_contact_id = fields.Many2one(
        "res.partner", string="Contact Person",
        domain="[('parent_id', '=', id)]",
    )
    ahps_alternative_contact_id = fields.Many2one(
        "res.partner", string="Alternative Contact",
        domain="[('parent_id', '=', id)]",
    )
    ahps_procurement_contact_id = fields.Many2one(
        "res.partner", string="Procurement Contact",
        domain="[('parent_id', '=', id)]",
        help="Receives quotations, sends purchase orders and coordinates deliveries.",
    )
    ahps_finance_contact_id = fields.Many2one(
        "res.partner", string="Finance Contact",
        domain="[('parent_id', '=', id)]",
        help="Receives invoices and processes payments.",
    )

    # ---- Documents --------------------------------------------------------
    ahps_kyc_document_ids = fields.One2many("ahps.kyc.document", "partner_id", string="KYC Documents")
    ahps_kyc_document_count = fields.Integer(compute="_compute_ahps_kyc_document_count")

    # ---- Duplicates -------------------------------------------------------
    ahps_duplicate_partner_ids = fields.Many2many(
        "res.partner", string="Possible Duplicates", compute="_compute_ahps_duplicate_partner_ids",
    )

    _ahps_customer_number_unique = models.Constraint(
        "UNIQUE(ahps_customer_number)",
        "This customer ID is already used by another customer.",
    )
    _ahps_supplier_number_unique = models.Constraint(
        "UNIQUE(ahps_supplier_number)",
        "This supplier ID is already used by another supplier.",
    )

    # ----------------------------------------------------------------------
    # Computes
    # ----------------------------------------------------------------------
    @api.depends("ahps_kyc_state", "commercial_partner_id.ahps_kyc_state")
    def _compute_ahps_kyc_commercial_state(self):
        for partner in self:
            partner.ahps_kyc_commercial_state = partner.commercial_partner_id.ahps_kyc_state

    @api.model
    def _ahps_category_roots(self):
        roots = self.env["res.partner.category"]
        for xmlid in ("ahps_kyc.partner_tag_end_user", "ahps_kyc.partner_tag_reseller"):
            tag = self.env.ref(xmlid, raise_if_not_found=False)
            if tag:
                roots |= tag
        return roots

    @api.depends("category_id")
    def _compute_ahps_category_tag_ids(self):
        tags = self.env["res.partner.category"].search([("id", "child_of", self._ahps_category_roots().ids)])
        for partner in self:
            partner.ahps_category_tag_ids = partner.category_id & tags

    def _compute_ahps_kyc_url(self):
        base_url = self.get_base_url() if self else ""
        for partner in self:
            token = partner.sudo().ahps_kyc_token
            partner.ahps_kyc_url = f"{base_url}/kyc/{partner.id}/{token}" if token and partner.id else False

    def _ahps_ensure_kyc_token(self):
        for partner in self.sudo():
            if not partner.ahps_kyc_token:
                partner.ahps_kyc_token = uuid.uuid4().hex
        return True

    @api.depends("ahps_kyc_document_ids")
    def _compute_ahps_kyc_document_count(self):
        for partner in self:
            partner.ahps_kyc_document_count = len(partner.ahps_kyc_document_ids)

    @api.model
    def _ahps_normalize_name(self, name):
        name = (name or "").lower()
        name = re.sub(r"\b(ltd|limited|plc|s\.?a\.?|s\.?co|co|inc|llc|company|the)\b\.?", " ", name)
        return re.sub(r"[^a-z0-9]+", "", name)

    @api.depends("name", "vat", "parent_id")
    def _compute_ahps_duplicate_partner_ids(self):
        for partner in self:
            duplicates = self.env["res.partner"]
            if not partner.parent_id and (partner.name or partner.vat):
                own_id = partner._origin.id
                domain_vat = []
                if partner.vat and partner.vat.strip() not in ("/", ""):
                    domain_vat = [("vat", "=ilike", partner.vat.strip())]
                candidates = self.env["res.partner"]
                if domain_vat:
                    candidates |= self.search(domain_vat + [("parent_id", "=", False), ("id", "!=", own_id)], limit=5)
                norm = self._ahps_normalize_name(partner.name)
                if len(norm) >= 4:
                    first_word = (partner.name or "").split()[0]
                    for cand in self.search(
                        [("parent_id", "=", False), ("id", "!=", own_id), ("name", "ilike", first_word)], limit=50,
                    ):
                        if self._ahps_normalize_name(cand.name) == norm:
                            candidates |= cand
                duplicates = candidates
            partner.ahps_duplicate_partner_ids = duplicates

    # ----------------------------------------------------------------------
    # Constraints / onchanges
    # ----------------------------------------------------------------------
    @api.constrains("ahps_customer_number", "ahps_supplier_number")
    def _check_ahps_customer_number(self):
        for partner in self:
            if partner.ahps_customer_number and not CUSTOMER_NUMBER_RE.match(partner.ahps_customer_number):
                raise ValidationError(self.env._(
                    "Customer ID %(number)s must follow the format YYYY.NNN (e.g. 2026.021).",
                    number=partner.ahps_customer_number,
                ))
            if partner.ahps_supplier_number and not CUSTOMER_NUMBER_RE.match(partner.ahps_supplier_number):
                raise ValidationError(self.env._(
                    "Supplier ID %(number)s must follow the format YYYY.NNN (e.g. 2026.066).",
                    number=partner.ahps_supplier_number,
                ))

    # ----------------------------------------------------------------------
    # KYC workflow
    # ----------------------------------------------------------------------
    def _ahps_check_kyc_company(self):
        for partner in self:
            if partner.parent_id:
                raise UserError(self.env._(
                    "KYC is managed on the company. Open %(company)s to manage its KYC.",
                    company=partner.commercial_partner_id.display_name,
                ))

    def _ahps_get_kyc_missing_information(self):
        """Return the list of missing KYC items for this company."""
        self.ensure_one()
        _ = self.env._
        is_supplier = self.ahps_registration_type == "supplier"
        checks = [
            (self.name, _("Company name")),
            (self.street or self.ahps_postal_address, _("Physical or postal address")),
            (self.city, _("City")),
            (self.country_id, _("Country")),
            (self.phone, _("Phone number")),
            (self.email, _("Email address")),
            (self.vat, _("Tax Identification Number (TIN)")),
            (self.ahps_company_registry, _("Company registration number")),
            (self.ahps_main_contact_id, _("Contact person")),
        ]
        if is_supplier:
            checks += [
                (self.ahps_authorized_contact_id, _("Authorized person")),
                (self.bank_ids, _("Bank account")),
            ]
        else:
            checks += [
                (self.ahps_category_tag_ids, _("Customer category tag (End User sector or Reseller)")),
                (self.ahps_procurement_contact_id, _("Procurement contact")),
                (self.ahps_finance_contact_id, _("Finance contact")),
            ]
        missing = [label for value, label in checks if not value]
        attached_types = self.ahps_kyc_document_ids.document_type_id
        for doc_type in self.env["ahps.kyc.document.type"]._ahps_required_types(self.ahps_registration_type):
            if doc_type not in attached_types:
                missing.append(_("Document: %s", doc_type.name))
        return missing

    def action_ahps_kyc_send_request(self):
        """Open the email composer to send the blank KYC form to the customer."""
        self.ensure_one()
        self._ahps_check_kyc_company()
        self._ahps_ensure_kyc_token()
        template = self.env.ref("ahps_kyc.mail_template_ahps_kyc_request", raise_if_not_found=False)
        ctx = {
            "default_model": "res.partner",
            "default_res_ids": self.ids,
            "default_template_id": template.id if template else False,
            "default_composition_mode": "comment",
            "ahps_kyc_mark_requested": True,
        }
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": ctx,
        }

    def _message_post_after_hook(self, message):
        # mark the KYC as requested once the request email is actually sent
        if self.env.context.get("ahps_kyc_mark_requested"):
            self.filtered(lambda p: p.ahps_kyc_state in ("not_started", "rejected")).write({
                "ahps_kyc_state": "requested",
                "ahps_kyc_requested_date": fields.Datetime.now(),
            })
        return super()._message_post_after_hook(message)

    def action_ahps_kyc_mark_requested(self):
        self._ahps_check_kyc_company()
        self._ahps_ensure_kyc_token()
        self.write({"ahps_kyc_state": "requested", "ahps_kyc_requested_date": fields.Datetime.now()})

    def action_ahps_kyc_submit(self):
        self._ahps_check_kyc_company()
        for partner in self:
            missing = partner._ahps_get_kyc_missing_information()
            if missing:
                raise UserError(self.env._(
                    "The KYC of %(name)s cannot be submitted. Missing information:\n- %(items)s",
                    name=partner.display_name, items="\n- ".join(missing),
                ))
        self._ahps_kyc_mark_submitted()

    def _ahps_kyc_mark_submitted(self):
        self.write({
            "ahps_kyc_state": "submitted",
            "ahps_kyc_submitted_date": fields.Datetime.now(),
            "ahps_kyc_rejection_reason": False,
        })
        reviewers = self.env.ref("ahps_kyc.group_ahps_kyc_manager").all_user_ids.filtered(lambda u: not u.share and u.active)
        for partner in self:
            open_reviews = partner.activity_ids.filtered(lambda a: a.summary == self.env._("Review KYC")).user_id
            for user in reviewers - open_reviews:
                partner.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=self.env._("Review KYC"),
                    note=self.env._("The KYC of %s has been submitted for review.", partner.display_name),
                )

    def _ahps_check_kyc_manager(self):
        if not self.env.user.has_group("ahps_kyc.group_ahps_kyc_manager"):
            raise UserError(self.env._("Only KYC Managers can approve or reject a KYC."))

    def _ahps_next_customer_number(self, registration_date):
        """Next customer ID: registration year + running number.

        The running number continues after the highest number already used, so imported
        customers (e.g. up to 2026.237) are followed by 238 without manual set-up.
        """
        return self._ahps_next_number("ahps_customer_number", "ahps.customer.number", registration_date)

    def _ahps_next_supplier_number(self, registration_date):
        """Next supplier ID, same logic as the customer ID with its own running number."""
        return self._ahps_next_number("ahps_supplier_number", "ahps.supplier.number", registration_date)

    def _ahps_next_number(self, field_name, sequence_code, registration_date):
        sequence = self.env["ir.sequence"].sudo().search([("code", "=", sequence_code)], limit=1)
        if not sequence:
            raise UserError(self.env._("The sequence '%s' is missing.", sequence_code))
        self.env.flush_all()
        # field_name is one of our two fixed column names, never user input
        self.env.cr.execute(f"""
            SELECT MAX(CAST(SPLIT_PART({field_name}, '.', 2) AS INTEGER))
              FROM res_partner
             WHERE {field_name} ~ '^[0-9]{{4}}\\.[0-9]+$'
        """)
        highest = self.env.cr.fetchone()[0] or 0
        if sequence.number_next_actual <= highest:
            sequence.number_next_actual = highest + 1
        return f"{registration_date.year}.{sequence.next_by_id()}"

    def action_ahps_kyc_approve(self):
        self._ahps_check_kyc_manager()
        self._ahps_check_kyc_company()
        today = fields.Date.context_today(self)
        for partner in self:
            if partner.ahps_kyc_state != "submitted":
                raise UserError(self.env._("Only submitted KYCs can be approved (%s).", partner.display_name))
            vals = {
                "ahps_kyc_state": "approved",
                "ahps_kyc_approved_date": fields.Datetime.now(),
                "ahps_kyc_approved_by_id": self.env.user.id,
                "ahps_kyc_rejection_reason": False,
            }
            reg_date = partner.ahps_registration_date or today
            if not partner.ahps_registration_date:
                vals["ahps_registration_date"] = reg_date
            if partner.ahps_registration_type == "supplier":
                if not partner.ahps_supplier_number:
                    vals["ahps_supplier_number"] = partner._ahps_next_supplier_number(reg_date)
                if not partner.supplier_rank:
                    vals["supplier_rank"] = 1
            else:
                if not partner.ahps_customer_number:
                    vals["ahps_customer_number"] = partner._ahps_next_customer_number(reg_date)
                if not partner.customer_rank:
                    vals["customer_rank"] = 1
            partner.write(vals)
            partner.activity_feedback(["mail.mail_activity_data_todo"],
                                      feedback=self.env._("KYC approved"))
        return True

    def action_ahps_kyc_reject(self):
        self._ahps_check_kyc_manager()
        self._ahps_check_kyc_company()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reject KYC"),
            "res_model": "ahps.kyc.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_partner_ids": self.ids},
        }

    def _ahps_kyc_do_reject(self, reason, notify=False):
        self.write({"ahps_kyc_state": "rejected", "ahps_kyc_rejection_reason": reason})
        template = self.env.ref("ahps_kyc.mail_template_ahps_kyc_rejected", raise_if_not_found=False)
        for partner in self:
            partner.message_post(body=self.env._("KYC rejected: %s", reason))
            partner.activity_feedback(["mail.mail_activity_data_todo"],
                                      feedback=self.env._("KYC rejected"))
            if notify and template and partner.email:
                partner._ahps_ensure_kyc_token()
                partner.message_post_with_source(template, subtype_xmlid="mail.mt_comment")

    def action_ahps_kyc_reset(self):
        self._ahps_check_kyc_manager()
        self.write({"ahps_kyc_state": "requested", "ahps_kyc_rejection_reason": False})

    def action_ahps_view_kyc_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("KYC Documents"),
            "res_model": "ahps.kyc.document",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    # ----------------------------------------------------------------------
    # Helpers used by other modules / reports
    # ----------------------------------------------------------------------
    def _ahps_kyc_is_approved(self):
        self.ensure_one()
        return self.commercial_partner_id.ahps_kyc_state == "approved"

    def _ahps_check_kyc_approved(self, action_label):
        """Raise if the KYC of these partners' companies is not approved."""
        for partner in self.commercial_partner_id:
            company = self.env.company
            if not company.ahps_kyc_required:
                continue
            if partner.ahps_kyc_state != "approved":
                state = dict(KYC_STATES).get(partner.ahps_kyc_state)
                raise UserError(self.env._(
                    "You cannot %(action)s for %(customer)s: the customer's KYC is not approved "
                    "(status: %(state)s).\nComplete and approve the KYC on the customer first.",
                    action=action_label, customer=partner.display_name, state=state,
                ))
