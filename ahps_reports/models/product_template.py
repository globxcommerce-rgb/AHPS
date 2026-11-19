from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ahps_hs_code = fields.Char(string="HS Code (Customs Tariff)", help="Printed in the 'Cust. Tariff' column of invoices.")
    ahps_country_of_origin_id = fields.Many2one("res.country", string="Country of Origin")
    ahps_charge_type = fields.Selection(
        [("shipping", "Shipping / Freight"), ("other", "Other Charges")],
        string="Document Charge Type",
        help="How this product is totalled on aHPS quotations and PFIs: shipping lines go to "
             "'Shipping' (Total CPT), other charges to 'Others'. Leave empty for goods and services.",
    )
