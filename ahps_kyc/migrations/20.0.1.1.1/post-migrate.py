from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Attach the files of existing KYC documents to their company (Files of the chatter)."""
    env = api.Environment(cr, SUPERUSER_ID, {"ahps_kyc_no_post": True})
    env["ahps.kyc.document"].search([("partner_attachment_id", "=", False)])._ahps_attach_to_partner(post=False)
