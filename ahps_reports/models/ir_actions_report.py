from odoo import models

# Documents re-designed by aHPS. Any report action that prints one of them uses the aHPS paper
# format, also actions added by other modules (e.g. the "Quotation / Order" action of the
# PDF Quote Builder, which replaces the standard quotation print button).
AHPS_REPORTS = {
    "sale.report_saleorder",
    "sale.report_saleorder_raw",
    "sale.report_saleorder_pro_forma",
    "account.report_invoice",
    "account.report_invoice_with_payments",
    "purchase.report_purchaseorder",
    "purchase.report_purchasequotation",
}


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def get_paperformat(self):
        if not self.paperformat_id and self.report_name in AHPS_REPORTS:
            ahps_format = self.env.ref("ahps_reports.paperformat_ahps_a4", raise_if_not_found=False)
            if ahps_format:
                return ahps_format
        return super().get_paperformat()

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == "sale.report_saleorder_pro_forma" and res_ids:
            self.env["sale.order"].browse(res_ids)._ahps_ensure_pfi_number()
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
