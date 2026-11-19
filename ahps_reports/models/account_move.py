from odoo import api, fields, models


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "ahps.report.mixin"]

    ahps_port_loading = fields.Char(string="Port of Loading")
    ahps_final_destination = fields.Char(string="Final Destination")

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.move_type in ("out_invoice", "out_refund"):
            return "ahps_reports.report_invoice_document"
        return super()._get_name_invoice_report()

    # ---- report helpers ---------------------------------------------------
    def _ahps_sale_orders(self):
        return self.invoice_line_ids.sale_line_ids.order_id

    def _ahps_report_rows(self, min_rows=38):
        self.ensure_one()
        lines = self.invoice_line_ids.sorted("sequence")
        return self._ahps_build_rows(lines, self.currency_id, "quantity", min_rows=min_rows)

    def _ahps_report_totals(self):
        self.ensure_one()
        cur = self.currency_id
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        charges = self._ahps_charge_totals(lines)
        discount = sum(l.quantity * l.price_unit * (l.discount or 0.0) / 100.0 for l in lines)
        tax = self._ahps_tax_info(lines, "tax_ids")
        sign = -1 if self.move_type == "out_refund" else 1
        vat = other_taxes = 0.0
        for line in self.line_ids.filtered(lambda l: l.display_type == "tax"):
            amount = -line.amount_currency * sign
            tax_name = ("%s %s" % (line.tax_line_id.name or "", line.tax_line_id.tax_group_id.name or "")).upper()
            if "VAT" in tax_name:
                vat += amount
            else:
                other_taxes += amount
        return {
            "net": self._ahps_fmt_amount(self.amount_untaxed - charges["other"], cur, dash_if_zero=False),
            "discount": self._ahps_fmt_amount(discount, cur) if discount else "",
            "vat": self._ahps_fmt_amount(vat, cur),
            "vat_label": "VAT (%s)" % tax["rate"] if vat else "VAT",
            "other_taxes": self._ahps_fmt_amount(other_taxes, cur),
            "others": self._ahps_fmt_amount(charges["other"], cur) if charges["other"] else "",
            "total": self._ahps_fmt_amount(self.amount_total, cur, dash_if_zero=False),
            "symbol": cur.symbol,
        }

    def _ahps_delivery_terms(self):
        self.ensure_one()
        if not self.invoice_incoterm_id:
            return ""
        return " ".join(p for p in (self.invoice_incoterm_id.code, self.incoterm_location) if p)
