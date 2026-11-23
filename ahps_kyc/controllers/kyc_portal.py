import base64
import logging

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import consteq, email_normalize

_logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per document
ALLOWED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")

# contact roles on the form: prefix -> (partner field, label, required for customer, required for supplier)
CONTACT_ROLES = [
    ("contact", "ahps_main_contact_id", "Contact Person", True, True),
    ("authorized", "ahps_authorized_contact_id", "Authorized Person", False, True),
    ("procurement", "ahps_procurement_contact_id", "Procurement Department", True, False),
    ("finance", "ahps_finance_contact_id", "Finance Department", True, False),
    ("alternative", "ahps_alternative_contact_id", "Alternative Contact", False, False),
]


class AhpsKycPortal(http.Controller):

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route("/kyc/<int:partner_id>/<string:token>", type="http", auth="public", website=False,
                methods=["GET"], sitemap=False)
    def kyc_form(self, partner_id, token, **kw):
        partner = self._get_partner(partner_id, token)
        if not partner:
            return request.not_found()
        if partner.ahps_kyc_state in ("submitted", "approved"):
            return self._render("ahps_kyc.portal_kyc_done", partner=partner)
        return self._render_form(partner=partner, values=self._values_from_partner(partner), errors=[])

    @http.route("/kyc/<int:partner_id>/<string:token>", type="http", auth="public", website=False,
                methods=["POST"], sitemap=False)
    def kyc_submit(self, partner_id, token, **post):
        partner = self._get_partner(partner_id, token)
        if not partner:
            return request.not_found()
        if partner.ahps_kyc_state in ("submitted", "approved"):
            return self._render("ahps_kyc.portal_kyc_done", partner=partner)
        return self._process(partner, post)

    @http.route("/kyc/register", type="http", auth="public", website=False, methods=["GET", "POST"], sitemap=False)
    def kyc_register(self, **post):
        company = request.env["res.company"].sudo().search([], limit=1)
        if not company.ahps_kyc_public_registration:
            return request.not_found()
        if request.httprequest.method == "GET":
            values = {"registration_type": post.get("type") if post.get("type") in ("customer", "supplier") else "customer"}
            return self._render_form(partner=None, values=values, errors=[])
        if post.get("website_url"):  # honeypot: humans never fill this hidden field
            return self._render("ahps_kyc.portal_kyc_done", partner=None)
        return self._process(None, post)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_partner(self, partner_id, token):
        partner = request.env["res.partner"].sudo().browse(partner_id).exists()
        if not partner or not partner.ahps_kyc_token or not token or not consteq(partner.ahps_kyc_token, token):
            return None
        return partner

    def _render(self, template, **values):
        company = request.env["res.company"].sudo().search([], limit=1)
        values.setdefault("company", company)
        return request.render(template, values)

    def _render_form(self, partner, values, errors):
        env = request.env
        end_user = env.ref("ahps_kyc.partner_tag_end_user", raise_if_not_found=False)
        reseller = env.ref("ahps_kyc.partner_tag_reseller", raise_if_not_found=False)
        sectors = env["res.partner.category"].sudo().search([("parent_id", "=", end_user.id)]) if end_user else []
        doc_types = env["ahps.kyc.document.type"].sudo().search([("portal_visible", "=", True)])
        countries = env["res.country"].sudo().search([])
        currencies = env["res.currency"].sudo().search([("active", "=", True)])
        return self._render(
            "ahps_kyc.portal_kyc_form",
            partner=partner,
            values=values,
            errors=errors,
            end_user=end_user,
            reseller=reseller,
            sectors=sectors,
            doc_types=doc_types,
            countries=countries,
            currencies=currencies,
            contact_roles=CONTACT_ROLES,
            existing_docs=partner.ahps_kyc_document_ids if partner else env["ahps.kyc.document"],
            action_url=f"/kyc/{partner.id}/{partner.ahps_kyc_token}" if partner else "/kyc/register",
        )

    def _values_from_partner(self, partner):
        """Pre-fill the form with what aHPS already knows about the company."""
        values = {
            "registration_type": partner.ahps_registration_type or "customer",
            "name": partner.name or "",
            "company_registry": partner.ahps_company_registry or "",
            "vat": partner.vat or "",
            "phone": partner.phone or "",
            "email": partner.email or "",
            "website": partner.website or "",
            "company_group": partner.ahps_company_group_name or "",
            "street": partner.street or "",
            "street2": partner.street2 or "",
            "city": partner.city or "",
            "country_id": partner.country_id.id or "",
            "postal_address": partner.ahps_postal_address or "",
            "invoice_same": "on",
            "delivery_same": "on",
        }
        tags = partner.ahps_category_tag_ids
        reseller = request.env.ref("ahps_kyc.partner_tag_reseller", raise_if_not_found=False)
        if reseller and reseller in tags:
            values["category"] = "reseller"
        elif tags:
            values["category"] = "end_user"
            sector = tags.filtered(lambda t: t.parent_id)[:1]
            values["sector_id"] = sector.id or ""
        for prefix, field_name, _label, _rc, _rs in CONTACT_ROLES:
            contact = partner[field_name]
            if contact:
                values.update({
                    f"{prefix}_name": contact.name or "",
                    f"{prefix}_function": contact.function or "",
                    f"{prefix}_email": contact.email or "",
                    f"{prefix}_phone": contact.phone or "",
                })
        for addr_type in ("invoice", "delivery"):
            addr = partner.child_ids.filtered(lambda c: c.type == addr_type)[:1]
            if addr:
                values.update({
                    f"{addr_type}_same": "",
                    f"{addr_type}_street": addr.street or "",
                    f"{addr_type}_city": addr.city or "",
                    f"{addr_type}_country_id": addr.country_id.id or "",
                })
        return values

    def _validate(self, post):
        errors = []
        reg_type = post.get("registration_type")
        if reg_type not in ("customer", "supplier"):
            errors.append("Please choose whether you register as a customer or a supplier.")
            reg_type = "customer"
        required = [
            ("name", "Company name"), ("company_registry", "Company registration number"),
            ("vat", "Tax Identification Number (TIN)"), ("phone", "Company phone"),
            ("email", "Company email"), ("street", "Physical address"), ("city", "City"),
            ("country_id", "Country"), ("declaration_name", "Name of the person making the declaration"),
            ("declaration_function", "Position of the person making the declaration"),
        ]
        if reg_type == "supplier":
            required += [("bank_name", "Bank name"), ("bank_account", "Bank account number")]
        else:
            required += [("category", "Type of company (End User or Reseller)")]
            if post.get("category") == "end_user":
                required += [("sector_id", "Sector")]
        for key, label in required:
            if not (post.get(key) or "").strip():
                errors.append(f"{label} is required.")
        if post.get("email") and not email_normalize(post.get("email")):
            errors.append("The company email address is not valid.")
        for prefix, _field, label, req_customer, req_supplier in CONTACT_ROLES:
            if post.get(f"{prefix}_same"):
                continue
            needed = req_supplier if reg_type == "supplier" else req_customer
            filled = any((post.get(f"{prefix}_{k}") or "").strip() for k in ("name", "email", "phone"))
            if needed or filled:
                if not (post.get(f"{prefix}_name") or "").strip():
                    errors.append(f"{label}: name is required.")
                if not (post.get(f"{prefix}_email") or "").strip():
                    errors.append(f"{label}: email is required.")
                elif not email_normalize(post.get(f"{prefix}_email")):
                    errors.append(f"{label}: email address is not valid.")
        for addr_type, label in (("invoice", "Invoice address"), ("delivery", "Delivery address")):
            if not post.get(f"{addr_type}_same"):
                for key, sub in (("street", "street"), ("city", "city"), ("country_id", "country")):
                    if not (post.get(f"{addr_type}_{key}") or "").strip():
                        errors.append(f"{label}: {sub} is required (or tick 'same as physical address').")
        if not post.get("declaration"):
            errors.append("Please confirm the declaration.")
        return errors, reg_type

    def _uploaded_documents(self, reg_type, partner):
        """Validate uploaded files. Returns (documents to create, errors)."""
        env = request.env
        files = request.httprequest.files
        docs, errors = [], []
        existing_types = partner.ahps_kyc_document_ids.document_type_id if partner else env["ahps.kyc.document.type"]
        for doc_type in env["ahps.kyc.document.type"].sudo()._ahps_types_for(reg_type).filtered("portal_visible"):
            upload = files.get(f"doc_{doc_type.id}")
            if upload and upload.filename:
                name = upload.filename
                content = upload.read()
                if not name.lower().endswith(ALLOWED_EXTENSIONS):
                    errors.append(f"{doc_type.name}: only PDF, JPG or PNG files are accepted.")
                elif len(content) > MAX_FILE_SIZE:
                    errors.append(f"{doc_type.name}: the file is larger than 10 MB.")
                elif not content:
                    errors.append(f"{doc_type.name}: the file is empty.")
                else:
                    docs.append({"document_type_id": doc_type.id, "attachment": base64.b64encode(content).decode(),
                                 "attachment_name": name})
            elif doc_type.required and doc_type not in existing_types:
                errors.append(f"{doc_type.name} is required.")
        return docs, errors

    def _process(self, partner, post):
        errors, reg_type = self._validate(post)
        docs, doc_errors = self._uploaded_documents(reg_type, partner)
        errors += doc_errors
        if errors:
            return self._render_form(partner=partner, values=post, errors=errors)
        Partner = request.env["res.partner"].sudo()
        is_new = partner is None
        try:
            with request.env.cr.savepoint():
                if partner is None:
                    partner = Partner.create({"name": post["name"].strip(), "ahps_kyc_state": "requested"})
                    partner._ahps_ensure_kyc_token()
                self._apply(partner, post, reg_type, docs)
        except (UserError, ValidationError) as e:
            _logger.info("KYC form for partner %s rejected: %s", partner and partner.id, e)
            return self._render_form(partner=None if is_new else partner, values=post,
                                     errors=[str(e.args[0]) if e.args else str(e)])
        # redirect after a successful submit, so refreshing the page or going back cannot post the form again
        return request.redirect(f"/kyc/{partner.id}/{partner.ahps_kyc_token}", code=303)

    def _apply(self, partner, post, reg_type, docs):
        env = request.env
        get = lambda key: (post.get(key) or "").strip()
        country_id = int(get("country_id")) if get("country_id").isdigit() else False
        vals = {
            "name": get("name"),
            "ahps_registration_type": reg_type,
            "ahps_company_registry": get("company_registry"),
            "phone": get("phone"),
            "email": get("email"),
            "website": get("website") or False,
            "ahps_company_group_name": get("company_group") or False,
            "street": get("street"),
            "street2": get("street2") or False,
            "city": get("city"),
            "country_id": country_id,
            "ahps_postal_address": get("postal_address") or False,
        }
        partner.write(vals)
        try:
            with env.cr.savepoint():
                partner.write({"vat": get("vat")})
        except ValidationError as e:
            raise ValidationError(f"Tax Identification Number: {e.args[0] if e.args else e}") from e

        # customer category tags
        if reg_type == "customer":
            roots = partner._ahps_category_roots()
            ahps_tags = env["res.partner.category"].sudo().search([("id", "child_of", roots.ids)])
            new_tags = env["res.partner.category"]
            if get("category") == "reseller":
                new_tags = env.ref("ahps_kyc.partner_tag_reseller")
            elif get("category") == "end_user":
                new_tags = env.ref("ahps_kyc.partner_tag_end_user")
                if get("sector_id").isdigit():
                    new_tags |= env["res.partner.category"].sudo().browse(int(get("sector_id"))).exists() & ahps_tags
            partner.category_id = [(3, t.id) for t in partner.category_id & ahps_tags] + [(4, t.id) for t in new_tags]

        # contact persons (related contacts)
        main_contact = False
        for prefix, field_name, label, _rc, _rs in CONTACT_ROLES:
            if post.get(f"{prefix}_same") and main_contact:
                partner[field_name] = main_contact
                continue
            name = get(f"{prefix}_name")
            if not name:
                continue
            contact_vals = {
                "name": name,
                "function": get(f"{prefix}_function") or False,
                "email": get(f"{prefix}_email") or False,
                "phone": get(f"{prefix}_phone") or False,
            }
            contact = partner[field_name]
            if not contact:
                email = email_normalize(contact_vals["email"] or "")
                contact = partner.child_ids.filtered(
                    lambda c: c.type == "contact" and (
                        (email and email_normalize(c.email or "") == email) or c.name.strip().lower() == name.lower()))[:1]
            if contact:
                contact.write(contact_vals)
            else:
                contact = env["res.partner"].sudo().create(dict(contact_vals, parent_id=partner.id, type="contact"))
            partner[field_name] = contact
            if prefix == "contact":
                main_contact = contact

        # invoice / delivery addresses
        for addr_type, label in (("invoice", "Invoice Address"), ("delivery", "Delivery Address")):
            existing = partner.child_ids.filtered(lambda c: c.type == addr_type)[:1]
            if post.get(f"{addr_type}_same"):
                continue
            cid = get(f"{addr_type}_country_id")
            addr_vals = {
                "street": get(f"{addr_type}_street"),
                "city": get(f"{addr_type}_city"),
                "country_id": int(cid) if cid.isdigit() else False,
            }
            if existing:
                existing.write(addr_vals)
            else:
                env["res.partner"].sudo().create(dict(addr_vals, parent_id=partner.id, type=addr_type))

        # supplier bank details
        if reg_type == "supplier" and get("bank_account"):
            bank_vals = {
                "bank_name": get("bank_name"),
                "bank_bic": get("bank_swift") or False,
                "street": get("bank_address") or False,
                "holder_name": get("name"),
                "note": ("IBAN: " + get("bank_iban")) if get("bank_iban") else False,
            }
            Bank = env["res.partner.bank"].sudo()
            if get("bank_currency_id").isdigit() and "ahps_currency_id" in Bank._fields:
                bank_vals["ahps_currency_id"] = int(get("bank_currency_id"))
            bank = partner.bank_ids.filtered(lambda b: b.account_number == get("bank_account"))[:1]
            if bank:
                bank.write(bank_vals)
            else:
                Bank.create(dict(bank_vals, partner_id=partner.id, account_number=get("bank_account")))

        # documents
        if docs:
            replaced = partner.ahps_kyc_document_ids.filtered(
                lambda d: d.document_type_id.id in {doc["document_type_id"] for doc in docs})
            replaced.sudo().unlink()
            env["ahps.kyc.document"].sudo().create([dict(d, partner_id=partner.id) for d in docs])

        partner.write({
            "ahps_kyc_submitted_online": True,
            "ahps_kyc_declared_by": get("declaration_name"),
            "ahps_kyc_declared_position": get("declaration_function"),
            "ahps_kyc_declaration_date": fields.Datetime.now(),
        })
        partner.message_post(body=f"KYC form submitted online by {get('declaration_name')} ({get('declaration_function')}).")
        partner._ahps_kyc_mark_submitted()
