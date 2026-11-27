from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "ahps.report.mixin"]

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
    ahps_fx_risk_factor = fields.Float(
        string="FX Risk Factor (%)", digits=(5, 2),
        default=lambda self: self.env.company.ahps_fx_risk_factor,
        help="Margin added to the day's exchange rate to cover currency movements until payment: "
             "quote rate = day's rate x (1 + factor). E.g. 140 with 3% gives 144.20. "
             "You can still type your own exchange rate afterwards.",
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
    ahps_purchase_order_ids = fields.One2many(
        "purchase.order", "ahps_sale_order_id", string="Linked Purchase Orders",
        help="Purchase orders placed with suppliers for this sales order.",
    )
    ahps_purchase_order_count = fields.Integer(compute="_compute_ahps_purchase_order_count")

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

    def _ahps_quote_rate(self, currency):
        """Rate used on the quotation: the day's rate plus the FX risk factor."""
        rate = self._ahps_system_rate(currency)
        if currency == self._ahps_base_currency():
            return rate
        return rate * (1.0 + (self.ahps_fx_risk_factor or 0.0) / 100.0)

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
        new_rate = self._ahps_quote_rate(new_currency)
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

    @api.onchange("ahps_fx_risk_factor")
    def _onchange_ahps_fx_risk_factor(self):
        for order in self:
            if order.state not in ("draft", "sent") or order.currency_id == order._ahps_base_currency():
                continue
            new_rate = order._ahps_quote_rate(order.currency_id)
            for line, (price, technical) in order._ahps_rate_change_prices(new_rate).items():
                line.technical_price_unit = technical
                line.price_unit = price
            order.ahps_fx_rate = new_rate
            order.ahps_fx_applied_rate = new_rate

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
        elif "ahps_fx_risk_factor" in vals and "ahps_currency_id" not in vals:
            for order in self.filtered(lambda o: o.state in ("draft", "sent")):
                if order.currency_id != order._ahps_base_currency():
                    order._ahps_apply_rate(order._ahps_quote_rate(order.currency_id))
        if "incoterm" in vals:
            self.filtered(lambda o: o.state in ("draft", "sent"))._ahps_sync_shipping_line()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders.filtered("incoterm")._ahps_sync_shipping_line()
        return orders

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

    # ---- shipping line from the Incoterm ----------------------------------
    @api.model
    def _ahps_shipping_product(self):
        """Product used for the automatic shipping line (created on first use)."""
        Product = self.env["product.product"].sudo()
        product = Product.search([("ahps_charge_type", "=", "shipping"), ("sale_ok", "=", True)], limit=1)
        if not product:
            product = Product.create({
                "name": "Shipping Charges",
                "type": "service",
                "ahps_charge_type": "shipping",
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 0.0,
                "invoice_policy": "order",
            })
        return product

    def _ahps_needs_shipping(self):
        self.ensure_one()
        return bool(self.incoterm) and (self.incoterm.code or "").upper() != "EXW"

    def _ahps_shipping_line_values(self):
        self.ensure_one()
        product = self._ahps_shipping_product()
        return {
            "product_id": product.id,
            "name": "Shipping Charges (%s)" % self._ahps_delivery_terms(),
            "product_uom_qty": 1.0,
            "price_unit": 0.0,
            "ahps_auto_shipping": True,
            "sequence": max(self.order_line.mapped("sequence") or [10]) + 1,
        }

    def _ahps_sync_shipping_line(self):
        """Any Incoterm except EXW adds a 'Shipping Charges' line (price to fill in); EXW removes it."""
        for order in self:
            auto = order.order_line.filtered("ahps_auto_shipping")
            if order._ahps_needs_shipping():
                has_shipping = order.order_line.filtered(
                    lambda l: l.product_id.product_tmpl_id.ahps_charge_type == "shipping")
                if auto:
                    auto.write({"name": "Shipping Charges (%s)" % order._ahps_delivery_terms()})
                elif not has_shipping:
                    order.write({"order_line": [Command.create(order._ahps_shipping_line_values())]})
            elif auto:
                auto.unlink()

    @api.onchange("incoterm")
    def _onchange_ahps_incoterm_shipping(self):
        for order in self:
            if order.state not in ("draft", "sent"):
                continue
            auto = order.order_line.filtered("ahps_auto_shipping")
            if order._ahps_needs_shipping():
                has_shipping = order.order_line.filtered(
                    lambda l: l.product_id.product_tmpl_id.ahps_charge_type == "shipping")
                if auto:
                    auto.name = "Shipping Charges (%s)" % order._ahps_delivery_terms()
                elif not has_shipping:
                    order.order_line = [Command.create(order._ahps_shipping_line_values())]
            elif auto:
                order.order_line = [Command.delete(line.id) for line in auto]

    # ---- linked purchase orders -------------------------------------------
    @api.depends("ahps_purchase_order_ids")
    def _compute_ahps_purchase_order_count(self):
        for order in self:
            order.ahps_purchase_order_count = len(order.ahps_purchase_order_ids)

    def action_ahps_view_purchase_orders(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": self.env._("Purchase Orders"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("ahps_sale_order_id", "=", self.id)],
            "context": {"default_ahps_sale_order_id": self.id, "default_origin": self.name},
        }
        if len(self.ahps_purchase_order_ids) == 1:
            action.update(view_mode="form", res_id=self.ahps_purchase_order_ids.id)
        return action

    def _ahps_is_service_quote(self):
        """Mostly services (not counting shipping/other charges): prints the S/N column and a Subtotal."""
        self.ensure_one()
        products = self.order_line.filtered(
            lambda l: not l.display_type and l.product_id and not l.product_id.product_tmpl_id.ahps_charge_type
        ).product_id
        services = products.filtered(lambda p: p.type == "service")
        return bool(products) and len(services) > len(products) / 2

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

    # rows printed in the line grid (empty rows fill the page, as on the aHPS paper templates)
    _AHPS_QUOTE_ROWS = 44
    _AHPS_PFI_ROWS = 42

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
            "has_service": self._ahps_is_service_quote(),
        }

    def _ahps_delivery_terms(self):
        self.ensure_one()
        if not self.incoterm:
            return "N/A"
        return " ".join(p for p in (self.incoterm.code, self.incoterm_location) if p)



class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    ahps_auto_shipping = fields.Boolean(
        string="Automatic Shipping Line", copy=False,
        help="Added automatically because the Incoterm is not EXW; removed again if it is set to EXW.",
    )

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
