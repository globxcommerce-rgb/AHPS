from odoo import fields, models


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    ahps_source_pricelist_id = fields.Many2one(
        "product.pricelist", string="Converted From", readonly=True,
        help="Created automatically by the quotation currency switch: prices are those of this price list, "
             "converted at the day's exchange rate.",
    )
