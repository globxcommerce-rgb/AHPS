from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """1.0 -> 1.1: online KYC form. The signed paper form is no longer required;
    certificate of incorporation and tax registration are."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    kyc_form = env.ref("ahps_kyc.kyc_doc_type_kyc_form", raise_if_not_found=False)
    if kyc_form:
        kyc_form.write({"required": False, "portal_visible": False, "name": "Signed KYC Form (paper)"})
    for xmlid in ("ahps_kyc.kyc_doc_type_incorporation", "ahps_kyc.kyc_doc_type_tax"):
        doc_type = env.ref(xmlid, raise_if_not_found=False)
        if doc_type:
            doc_type.write({"required": True, "applies_to": "both"})
    other = env.ref("ahps_kyc.kyc_doc_type_other", raise_if_not_found=False)
    if other:
        other.portal_visible = False

    # the KYC request email now links to the online form; its data file is noupdate, so reload it
    from odoo.tools import convert_file
    convert_file(env, "ahps_kyc", "data/mail_template_data.xml", {}, mode="init", noupdate=True)
