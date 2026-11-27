import re

from odoo import api, models
from odoo.tools import float_is_zero, format_date


class AhpsReportMixin(models.AbstractModel):
    """Helpers shared by the aHPS document templates."""

    _name = "ahps.report.mixin"
    _description = "aHPS Report Helpers"

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    @api.model
    def _ahps_fmt_amount(self, amount, currency, dash_if_zero=True):
        if dash_if_zero and float_is_zero(amount or 0.0, precision_rounding=currency.rounding):
            return "-"
        return "{:,.{p}f}".format(amount or 0.0, p=currency.decimal_places)

    @api.model
    def _ahps_fmt_qty(self, qty):
        if qty is None:
            return ""
        if float(qty).is_integer():
            return str(int(qty))
        return ("%.3f" % qty).rstrip("0").rstrip(".")

    @api.model
    def _ahps_fmt_date(self, value, fmt="%d.%m.%Y"):
        if not value:
            return ""
        if hasattr(value, "date") and callable(value.date):
            value = value.date()
        return value.strftime(fmt)

    @api.model
    def _ahps_fmt_percent(self, value):
        if not value:
            return ""
        return ("%.2f" % value).rstrip("0").rstrip(".") + "%"

    # ------------------------------------------------------------------
    # Partners / addresses
    # ------------------------------------------------------------------
    @api.model
    def _ahps_address_lines(self, partner):
        """Address lines of a partner (company part only), as printed on aHPS documents."""
        partner = partner.commercial_partner_id if partner.parent_id and partner.type == "contact" else partner
        lines = []
        for value in (partner.ahps_postal_address if "ahps_postal_address" in partner._fields else False,
                      partner.street, partner.street2):
            if value and value not in lines:
                lines.append(value)
        city = " ".join(p for p in (partner.zip, partner.city) if p)
        if partner.state_id and partner.state_id.name not in city:
            city = ", ".join(p for p in (city, partner.state_id.name) if p)
        if city:
            lines.append(city)
        if partner.country_id:
            lines.append(partner.country_id.name)
        return lines

    @api.model
    def _ahps_attention(self, partner):
        """Person to address the document to: the contact itself, or the company's KYC contact."""
        if partner.parent_id:
            return partner
        commercial = partner.commercial_partner_id
        return commercial.ahps_main_contact_id if "ahps_main_contact_id" in commercial._fields else partner.browse()

    # ------------------------------------------------------------------
    # Lines grid
    # ------------------------------------------------------------------
    @api.model
    def _ahps_clean_description(self, name, product):
        """Description lines of an order line, without the [code] prefix (the code has its own column)."""
        name = (name or "").strip()
        code = product.default_code if product else False
        lines = [line.rstrip() for line in name.split("\n")]
        if code:
            prefix = "[%s]" % code
            lines = [l[len(prefix):].strip() if l.startswith(prefix) else l for l in lines]
        # Odoo 20 labels are "product name + description": drop a repeated first line
        if len(lines) > 1 and lines[0].strip() == lines[1].strip():
            lines.pop(0)
        return lines or [""]

    @api.model
    def _ahps_build_rows(self, lines, currency, qty_field, min_rows=0, part_number=None, spacer=True):
        """Turn order/invoice lines into the rows of the aHPS line grid.

        Each product line becomes one row with position, quantity, code and amounts,
        followed by one row per extra description line. Sections are underlined
        headings and notes are printed line by line, as in the aHPS templates.
        """
        rows = []
        pos = 0
        # notes after the last product (e.g. "Optional Documents") go to the bottom of the grid,
        # under the empty rows, as on the aHPS paper templates
        lines = list(lines)
        bottom_notes = []
        if min_rows:
            while lines and lines[-1].display_type == "line_note":
                bottom_notes.insert(0, lines.pop())
        for line in lines:
            display_type = line.display_type or "product"
            if display_type in ("line_section", "line_subsection"):
                rows.append({"desc": (line.name or "").strip(), "style": "section" if display_type == "line_section" else "subsection"})
                continue
            if display_type == "line_note":
                for text in (line.name or "").split("\n"):
                    rows.append({"desc": text, "style": "note"})
                continue
            if display_type != "product":
                continue
            pos += 1
            label = line.label if "label" in line._fields else line.name
            desc = self._ahps_clean_description(label or line.name or line.product_id.display_name, line.product_id)
            if spacer and pos > 1 and rows and rows[-1].get("style") != "section":
                rows.append({})
            product = line.product_id
            rows.append({
                "pos": "%02d" % pos,
                "qty": self._ahps_fmt_qty(line[qty_field]),
                "code": product.default_code or "",
                "part": part_number(line) if part_number else (product.default_code or ""),
                "tariff": product.product_tmpl_id.ahps_hs_code or "",
                "desc": desc[0],
                "price": self._ahps_fmt_amount(line.price_unit, currency, dash_if_zero=False),
                "disc": self._ahps_fmt_percent(line.discount) if "discount" in line._fields else "",
                "total": self._ahps_fmt_amount(line.price_subtotal, currency, dash_if_zero=False),
                "currency": currency.symbol,
                "style": "product",
            })
            for extra in desc[1:]:
                rows.append({"desc": extra, "style": "extra"})
        bottom = []
        for note in bottom_notes:
            texts = (note.name or "").split("\n")
            for i, text in enumerate(texts):
                bottom.append({"desc": text, "style": "note_title" if i == 0 and len(texts) > 1 else "note"})
        if bottom:
            bottom.append({})
        while len(rows) + len(bottom) < min_rows:
            rows.append({})
        return rows + bottom

    # ------------------------------------------------------------------
    # Taxes / totals
    # ------------------------------------------------------------------
    @api.model
    def _ahps_tax_info(self, lines, tax_field):
        taxes = lines.mapped(tax_field)
        percent_taxes = taxes.filtered(lambda t: t.amount_type == "percent")
        rates = sorted(set(percent_taxes.mapped("amount")))
        if any(rates):
            rates = [r for r in rates if r]
        is_wht = any(re.search(r"wht|withholding", (t.name or "") + " " + (t.description or ""), re.I) for t in taxes)
        return {
            "label": "WHT Rate" if is_wht else "VAT Rate",
            "short_label": "WHT" if is_wht else "VAT",
            "rate": ", ".join((self._ahps_fmt_percent(abs(r)) or "0%") for r in rates) if rates else "0%",
        }

    @api.model
    def _ahps_charge_totals(self, lines):
        """Split untaxed amounts by product charge type (goods/services, shipping, other)."""
        totals = {"goods": 0.0, "shipping": 0.0, "other": 0.0, "taxable": 0.0}
        for line in lines:
            if line.display_type and line.display_type != "product":
                continue
            charge = line.product_id.product_tmpl_id.ahps_charge_type or "goods"
            totals[charge] += line.price_subtotal
            tax_field = "tax_ids" if "tax_ids" in line._fields else "tax_id"
            if line[tax_field].filtered(lambda t: t.amount):
                totals["taxable"] += line.price_subtotal
        return totals
