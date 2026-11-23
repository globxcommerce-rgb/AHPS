from odoo import fields, models


class AhpsDocumentLogo(models.Model):
    _name = "ahps.document.logo"
    _description = "Logo printed on aHPS documents"
    _order = "usage, sequence, id"

    name = fields.Char(required=True)
    usage = fields.Selection(
        [("footer", "Partner logo (document footer)"), ("accreditation", "Accreditation badge (invoices)")],
        required=True, default="footer",
    )
    image = fields.Image(required=True, max_width=600, max_height=300)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", help="Leave empty to print it for every company.")
