from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "ahps.report.mixin"]

    ahps_end_user_id = fields.Many2one(
        "res.partner", string="End User", compute="_compute_ahps_end_user_id", store=True, readonly=False,
        help="Customer the goods are for. Printed on the RFQ. Filled from the linked sales order or dropship address.",
    )

    @api.depends("dest_address_id", "origin")
    def _compute_ahps_end_user_id(self):
        for order in self:
            partner = order.ahps_end_user_id
            sale_orders = self.env["sale.order"]
            if hasattr(order, "_get_sale_orders"):
                sale_orders = order._get_sale_orders()
            if sale_orders:
                partner = sale_orders[:1].partner_id.commercial_partner_id
            elif order.dest_address_id:
                partner = order.dest_address_id.commercial_partner_id
            elif order.origin and not partner:
                so = self.env["sale.order"].search([("name", "=", order.origin.split(",")[0].strip())], limit=1)
                partner = so.partner_id.commercial_partner_id
            order.ahps_end_user_id = partner

    # ---- report helpers ---------------------------------------------------
    def _ahps_vendor_part_number(self, line):
        seller = line.product_id.seller_ids.filtered(
            lambda s: s.partner_id == self.partner_id.commercial_partner_id and s.product_code
        )[:1]
        return seller.product_code or line.product_id.default_code or ""

    def _ahps_report_rows(self, min_rows=40, spacer=True):
        self.ensure_one()
        lines = self.order_line.sorted("sequence")
        return self._ahps_build_rows(lines, self.currency_id, "product_qty", min_rows=min_rows,
                                     part_number=self._ahps_vendor_part_number, spacer=spacer)

    def _ahps_report_totals(self):
        self.ensure_one()
        cur = self.currency_id
        lines = self.order_line.filtered(lambda l: not l.display_type)
        tax = self._ahps_tax_info(lines, "tax_ids" if "tax_ids" in lines._fields else "taxes_id")
        return {
            "untaxed": self._ahps_fmt_amount(self.amount_untaxed, cur, dash_if_zero=False),
            "tax": self._ahps_fmt_amount(self.amount_tax, cur) if self.amount_tax else "",
            "tax_label": "%s (%s)" % (tax["short_label"], tax["rate"]) if self.amount_tax else "VAT ( . . . %)",
            "total": self._ahps_fmt_amount(self.amount_total, cur, dash_if_zero=False),
            "symbol": cur.symbol,
        }

    def _ahps_payment_term_rows(self):
        self.ensure_one()
        rows = []
        for line in self.payment_term_id.line_ids:
            if line.value == "percent":
                amount = self._ahps_fmt_percent(line.value_amount) or "0%"
            else:
                amount = self._ahps_fmt_amount(line.value_amount, self.currency_id)
            if line.nb_days:
                label = "Net %s days" % line.nb_days
            else:
                label = "with the PO"
            rows.append((amount, label))
        if not rows and self.payment_term_id:
            rows.append(("", self.payment_term_id.name))
        return rows

    def _ahps_delivery_terms(self):
        self.ensure_one()
        if not self.incoterm_id:
            return ""
        return " ".join(p for p in (self.incoterm_id.code, self.incoterm_location) if p)
