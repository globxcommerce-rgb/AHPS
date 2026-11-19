from odoo import api, fields, models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "ahps.report.mixin"]

    ahps_quote_category = fields.Selection(
        [("instrument", "Instruments"), ("spare_parts", "Spare Parts"), ("service", "Service")],
        string="Quotation Category", compute="_compute_ahps_quote_category", store=True, readonly=False,
        help="Used to analyse quotations and revenue by category. Service quotations print "
             "the S/N column and a Subtotal.",
    )
    ahps_pfi_number = fields.Char(string="PFI No.", copy=False, readonly=True)
    ahps_pfi_date = fields.Date(string="PFI Date", copy=False)
    ahps_lead_time = fields.Char(string="Lead Time", help="e.g. 2-3 weeks after order confirmation")
    ahps_port_loading = fields.Char(string="Port of Loading")
    ahps_port_destination = fields.Char(string="Port of Destination")
    ahps_packing_details = fields.Char(string="Packing Details", help="e.g. 43 x 35 x 32 cm")
    ahps_gross_weight = fields.Char(string="Gross Weight", help="e.g. Approx. 8.0 Kg")

    @api.depends("order_line.product_id")
    def _compute_ahps_quote_category(self):
        for order in self:
            if order.ahps_quote_category:
                continue
            products = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id and not l.product_id.product_tmpl_id.ahps_charge_type
            ).product_id
            if not products:
                continue
            services = products.filtered(lambda p: p.type == "service")
            # documentation/handling services don't make a service quotation on their own
            if len(services) > len(products) / 2:
                order.ahps_quote_category = "service"
            else:
                order.ahps_quote_category = "instrument"

    def _ahps_ensure_pfi_number(self):
        for order in self.filtered(lambda o: not o.ahps_pfi_number):
            order.sudo().write({
                "ahps_pfi_number": self.env["ir.sequence"].next_by_code("ahps.pfi"),
                "ahps_pfi_date": order.ahps_pfi_date or fields.Date.context_today(order),
            })

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals.update({
            "ahps_port_loading": self.ahps_port_loading,
            "ahps_final_destination": self.ahps_port_destination or self.partner_shipping_id.country_id.name,
        })
        return vals

    # ---- report helpers ---------------------------------------------------
    def _ahps_report_rows(self, min_rows=30):
        self.ensure_one()
        return self._ahps_build_rows(self._get_order_lines_to_report(), self.currency_id, "product_uom_qty", min_rows=min_rows)

    def _ahps_report_totals(self):
        self.ensure_one()
        lines = self.order_line.filtered(lambda l: not l.display_type)
        charges = self._ahps_charge_totals(lines)
        tax = self._ahps_tax_info(lines, "tax_ids" if "tax_ids" in lines._fields else "tax_id")
        cur = self.currency_id
        exworks = charges["goods"]
        return {
            "exworks": self._ahps_fmt_amount(exworks, cur),
            "shipping": self._ahps_fmt_amount(charges["shipping"], cur),
            "cpt": self._ahps_fmt_amount(exworks + charges["shipping"], cur) if charges["shipping"] else "-",
            "subtotal": self._ahps_fmt_amount(charges["goods"] + charges["shipping"], cur),
            "taxable": self._ahps_fmt_amount(charges["taxable"], cur),
            "others": self._ahps_fmt_amount(charges["other"], cur),
            "tax_label": tax["label"],
            "tax_rate": tax["rate"],
            "tax_due": self._ahps_fmt_amount(self.amount_tax, cur),
            "total": self._ahps_fmt_amount(self.amount_total, cur, dash_if_zero=False),
            "symbol": cur.symbol,
            "has_service": self.ahps_quote_category == "service",
        }

    def _ahps_delivery_terms(self):
        self.ensure_one()
        if not self.incoterm:
            return "N/A"
        return " ".join(p for p in (self.incoterm.code, self.incoterm_location) if p)
