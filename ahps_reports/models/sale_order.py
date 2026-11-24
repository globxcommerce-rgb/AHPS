from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "ahps.report.mixin"]

    ahps_quote_category = fields.Selection(
        [("instrument", "Instruments"), ("spare_parts", "Spare Parts"), ("service", "Service")],
        string="Quotation Category", compute="_compute_ahps_quote_category", store=True, readonly=False,
        help="Used to analyse quotations and revenue by category. Service quotations print "
             "the S/N column and a Subtotal.",
    )
    ahps_currency_id = fields.Many2one(
        "res.currency", string="Quote Currency", compute="_compute_ahps_currency_id", store=True, readonly=False,
        precompute=True, domain="[('active', '=', True)]",
        help="Currency of the quotation. Changing it converts all prices from the current currency at the "
             "exchange rate of the quotation date and switches to the matching pricelist "
             "(based on the EUR price list).",
    )
    ahps_fx_rate = fields.Float(
        string="Exchange Rate", digits=(12, 6), copy=False,
        help="1 unit of the base price list currency (EUR) = this many units of the quotation currency. "
             "Filled with the day's rate when the quote currency is changed; type your own rate to "
             "recalculate all prices of this quotation at that rate.",
    )
    ahps_fx_applied_rate = fields.Float(
        string="Applied Rate", digits=(12, 6), copy=False,
        help="Technical: rate at which the current line prices are expressed.",
    )
    ahps_fx_rate_date = fields.Date(string="Rate Date", copy=False)
    ahps_fx_base_currency_id = fields.Many2one("res.currency", string="Base Currency", copy=False)
    ahps_pfi_number = fields.Char(string="PFI No.", copy=False, readonly=True)
    ahps_pfi_date = fields.Date(string="PFI Date", copy=False)
    ahps_lead_time = fields.Char(string="Lead Time", help="e.g. 2-3 weeks after order confirmation")
    ahps_port_loading = fields.Char(string="Port of Loading")
    ahps_port_destination = fields.Char(string="Port of Destination")
    ahps_packing_details = fields.Char(string="Packing Details", help="e.g. 43 x 35 x 32 cm")
    ahps_gross_weight = fields.Char(string="Gross Weight", help="e.g. Approx. 8.0 Kg")

    # ---- currency switch -----------------------------------------------------
    @api.depends("pricelist_id", "company_id")
    def _compute_ahps_currency_id(self):
        for order in self:
            order.ahps_currency_id = order.pricelist_id.currency_id or order.company_id.currency_id

    def _ahps_base_pricelist(self):
        self.ensure_one()
        return self.company_id.ahps_base_pricelist_id

    def _ahps_pricelist_for_currency(self, currency):
        """Pricelist to use for `currency`: the base (EUR) list itself, or a list derived from it."""
        self.ensure_one()
        Pricelist = self.env["product.pricelist"].sudo()
        base = self._ahps_base_pricelist()
        if base and base.currency_id == currency:
            return base
        company_domain = [("company_id", "in", (False, self.company_id.id))]
        if base:
            derived = Pricelist.search([("ahps_source_pricelist_id", "=", base.id), ("currency_id", "=", currency.id)] + company_domain, limit=1)
            if derived:
                return derived
            return Pricelist.create({
                "name": f"{base.name} in {currency.name}",
                "currency_id": currency.id,
                "company_id": base.company_id.id,
                "ahps_source_pricelist_id": base.id,
                "item_ids": [(0, 0, {
                    "applied_on": "3_global",
                    "compute_price": "discount",
                    "price_discount": 0.0,
                    "base": "pricelist",
                    "base_pricelist_id": base.id,
                })],
            })
        existing = Pricelist.search([("currency_id", "=", currency.id)] + company_domain, limit=1)
        return existing or Pricelist.create({"name": currency.name, "currency_id": currency.id})

    def _ahps_check_rate(self, currency, date):
        company_currency = self.company_id.currency_id
        if currency == company_currency:
            return
        has_rate = self.env["res.currency.rate"].sudo().search_count([
            ("currency_id", "=", currency.id), ("name", "<=", date),
            ("company_id", "in", (False, self.company_id.id)),
        ], limit=1)
        if not has_rate:
            raise UserError(self.env._(
                "There is no exchange rate for %(currency)s on or before %(date)s. "
                "Add it in Accounting > Configuration > Currencies before switching the quotation currency.",
                currency=currency.name, date=date,
            ))

    def _ahps_date(self):
        return fields.Date.to_date(self.date_order) or fields.Date.context_today(self)

    def _ahps_base_currency(self):
        return self._ahps_base_pricelist().currency_id or self.company_id.currency_id

    def _ahps_system_rate(self, currency):
        """Day's rate from Accounting: 1 unit of the base currency = this many units of `currency`."""
        base_currency = self._ahps_base_currency()
        if currency == base_currency:
            return 1.0
        date = self._ahps_date()
        self._ahps_check_rate(base_currency, date)
        self._ahps_check_rate(currency, date)
        return base_currency._convert(1.0, currency, self.company_id, date, round=False)

    def _ahps_current_rate(self):
        """Rate (base currency -> order currency) at which the current line prices are expressed."""
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        if currency == self._ahps_base_currency():
            return 1.0
        return self.ahps_fx_applied_rate or self.ahps_fx_rate or self._ahps_system_rate(currency)

    def _ahps_currency_change_values(self, new_currency):
        """Return (pricelist, {line: new price}, fx info) to convert this order to `new_currency`."""
        self.ensure_one()
        old_rate = self._ahps_current_rate()
        new_rate = self._ahps_system_rate(new_currency)
        factor = new_rate / old_rate if old_rate else 1.0
        pricelist = self._ahps_pricelist_for_currency(new_currency)
        prices = {
            line: (line.price_unit * factor, line.technical_price_unit * factor)
            for line in self.order_line.filtered(lambda l: not l.display_type)
        }
        return pricelist, prices, {
            "ahps_fx_rate": new_rate, "ahps_fx_applied_rate": new_rate, "ahps_fx_rate_date": self._ahps_date(),
            "ahps_fx_base_currency_id": self._ahps_base_currency().id,
        }

    def _ahps_rate_change_prices(self, new_rate):
        """{line: (price, technical price)} after changing the exchange rate of this order to `new_rate`."""
        self.ensure_one()
        old_rate = self._ahps_current_rate()
        if not new_rate or not old_rate or abs(new_rate - old_rate) < 1e-9:
            return {}
        factor = new_rate / old_rate
        return {
            line: (line.price_unit * factor, line.technical_price_unit * factor)
            for line in self.order_line.filtered(lambda l: not l.display_type)
        }

    @api.onchange("ahps_currency_id")
    def _onchange_ahps_currency_id(self):
        for order in self:
            new_currency = order.ahps_currency_id
            if not new_currency or new_currency == order.currency_id or order.state not in ("draft", "sent"):
                continue
            pricelist, prices, fx = order._ahps_currency_change_values(new_currency)
            order.pricelist_id = pricelist
            for line, (price, technical) in prices.items():
                line.technical_price_unit = technical
                line.price_unit = price
            order.update(fx)

    @api.onchange("ahps_fx_rate")
    def _onchange_ahps_fx_rate(self):
        for order in self:
            if order.state not in ("draft", "sent") or order.currency_id == order._ahps_base_currency():
                continue
            if order.ahps_fx_rate <= 0:
                order.ahps_fx_rate = order._ahps_current_rate()
                continue
            for line, (price, technical) in order._ahps_rate_change_prices(order.ahps_fx_rate).items():
                line.technical_price_unit = technical
                line.price_unit = price
            order.ahps_fx_applied_rate = order.ahps_fx_rate

    def write(self, vals):
        if "ahps_fx_rate" in vals and vals["ahps_fx_rate"] is not False and vals["ahps_fx_rate"] <= 0:
            raise UserError(self.env._("The exchange rate must be greater than zero."))
        res = super().write(vals)
        if "ahps_currency_id" in vals:
            for order in self:
                if order.ahps_currency_id and order.ahps_currency_id != order.currency_id and order.state in ("draft", "sent"):
                    order._ahps_apply_currency(order.ahps_currency_id, rate=vals.get("ahps_fx_rate"))
        if "ahps_fx_rate" in vals:
            for order in self.filtered(lambda o: o.state in ("draft", "sent")):
                order._ahps_apply_rate(order.ahps_fx_rate)
        return res

    def _ahps_apply_rate(self, rate):
        """Server-side rate change (same as the onchange, for imports and API calls)."""
        self.ensure_one()
        if not rate or self.currency_id == self._ahps_base_currency():
            return
        for line, (price, technical) in self._ahps_rate_change_prices(rate).items():
            line.write({"technical_price_unit": technical, "price_unit": price})
        if abs((self.ahps_fx_applied_rate or 0.0) - rate) > 1e-9:
            super(SaleOrder, self).write({"ahps_fx_applied_rate": rate, "ahps_fx_rate": rate})

    def _ahps_apply_currency(self, new_currency, rate=None):
        """Server-side currency switch (same as the onchange, for imports and API calls)."""
        self.ensure_one()
        pricelist, prices, fx = self._ahps_currency_change_values(new_currency)
        if rate and new_currency != self._ahps_base_currency():
            factor = rate / fx["ahps_fx_rate"]
            prices = {line: (p * factor, t * factor) for line, (p, t) in prices.items()}
            fx.update(ahps_fx_rate=rate, ahps_fx_applied_rate=rate)
        super(SaleOrder, self).write(dict(fx, pricelist_id=pricelist.id))
        for line, (price, technical) in prices.items():
            line.write({"technical_price_unit": technical, "price_unit": price})

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



class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _reset_price_unit(self):
        """Prices from the derived price list use the day's rate: apply the quote's own rate instead."""
        super()._reset_price_unit()
        order = self.order_id
        if not order or self.display_type or not order.ahps_fx_applied_rate or order.state not in ("draft", "sent"):
            return
        currency = order.currency_id
        if not currency or currency == order._ahps_base_currency():
            return
        system_rate = order._ahps_system_rate(currency)
        if system_rate and abs(order.ahps_fx_applied_rate - system_rate) > 1e-9:
            price = self.price_unit * order.ahps_fx_applied_rate / system_rate
            self.update({"price_unit": price, "technical_price_unit": price})
