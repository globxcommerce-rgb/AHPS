from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ahps_base_pricelist_id = fields.Many2one(
        "product.pricelist", string="Base Price List",
        help="Price list holding the standard (EUR) prices. When a quotation is switched to another currency, "
             "prices are converted from it at the day's exchange rate.",
    )
    ahps_registration_no = fields.Char(string="Certificate of Registration", help="Printed as 'Cert. of Registration' on aHPS documents.")
    ahps_doc_signatory = fields.Char(string="Document Signatory", default="J. Mbugua",
                                     help="Name printed on the signature line of quotations, PFIs and RFQs.")
    ahps_handling_charges = fields.Char(string="Handling Charges", default="EUR 50 for Orders below EUR 1,000")
    ahps_sales_phone = fields.Char(string="Sales Contact Phone", default="+254 727 629 623")
    ahps_sales_email = fields.Char(string="Sales Contact Email", default="info@helprosol.com")
    ahps_finance_email = fields.Char(string="Finance Contact Email", default="finance@helprosol.com")
    ahps_operations_contact = fields.Char(string="Operations Contact",
                                          default="Operations@helprosol.com / +254 701 400 200",
                                          help="Printed at the bottom of purchase orders.")
    ahps_po_special_note = fields.Text(string="PO Special Note",
                                       default="ORDERS TO BE SHIPPED OUTSIDE KENYA, SHOULD ALWAYS HAVE A SHIPPING INVOICE FROM AHPS LTD")
    ahps_po_invoice_contact_id = fields.Many2one("res.partner", string="PO Invoice Address Contact",
                                                 help="Printed as 'Att.' under the invoice address of purchase orders.")
    ahps_bank_account_ids = fields.Many2many("res.partner.bank", "ahps_company_bank_doc_rel", "company_id", "bank_id", string="Bank Accounts on Documents",
                                             help="Bank accounts printed under 'Bank Payment Details'. "
                                                  "Leave empty to print all bank accounts of the company.")
    ahps_show_footer_logos = fields.Boolean(string="Print Partner Logos", default=True,
                                            help="Print the Pentair / Yakima Chief / Doemens / ATEC logos at the bottom of quotations, PFIs and invoices.")
    ahps_show_accreditation = fields.Boolean(string="Print ISO/IEC 17025 Badge on Invoices", default=True)

    def _ahps_document_logos(self, usage="footer"):
        self.ensure_one()
        return self.env["ahps.document.logo"].sudo().search(
            [("usage", "=", usage), ("company_id", "in", (False, self.id))]
        )

    def _ahps_bank_accounts(self):
        self.ensure_one()
        return self.ahps_bank_account_ids or self.partner_id.bank_ids


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    ahps_currency_id = fields.Many2one(
        "res.currency", string="Account Currency",
        help="Currency printed next to the account number on aHPS documents, e.g. 204 240 1369 (KES). "
             "Defaults to the currency of the linked bank journal.",
    )

    def _ahps_currency(self):
        self.ensure_one()
        return self.ahps_currency_id or self.journal_id[:1].currency_id
