from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # customer IDs get a "C" prefix and supplier IDs an "S" prefix (2026.238 -> C2026.238)
    cr.execute(r"""
        UPDATE res_partner SET ahps_customer_number = 'C' || ahps_customer_number
         WHERE ahps_customer_number ~ '^[0-9]{4}\.[0-9]+$'
    """)
    cr.execute(r"""
        UPDATE res_partner SET ahps_supplier_number = 'S' || ahps_supplier_number
         WHERE ahps_supplier_number ~ '^[0-9]{4}\.[0-9]+$'
    """)
    env = api.Environment(cr, SUPERUSER_ID, {})
    # sector "Rest" is renamed "Others" (the tag data is noupdate)
    tag = env.ref("ahps_kyc.partner_tag_rest", raise_if_not_found=False)
    if tag and tag.name == "Rest":
        tag.name = "Others"
    env["res.partner"].invalidate_model(["ahps_customer_number", "ahps_supplier_number"])
