from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == "sale.report_saleorder_pro_forma" and res_ids:
            self.env["sale.order"].browse(res_ids)._ahps_ensure_pfi_number()
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
