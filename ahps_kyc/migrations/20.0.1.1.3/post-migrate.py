from odoo import SUPERUSER_ID, api
from odoo.tools import convert_file


def migrate(cr, version):
    """Reload the KYC emails: the request email now adapts to customers and suppliers."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    convert_file(env, "ahps_kyc", "data/mail_template_data.xml", {}, mode="init", noupdate=True)
