import json
from odoo import models, fields, api


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def button_generate_transfer_content(self):
        rec = self.env["ntp.transfer.content.generate.wizard"].create(
            {
                "template_type": "payslip",
                "model": "hr.payslip",
                "record_ids": json.dumps(self.slip_ids.ids)
            }
        )
        action = {
            "name": "Generate Transfer Content",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "ntp.transfer.content.generate.wizard",
            "views": [[False, "form"]],
            "context": {},
            "res_id": rec.id,
            "domain": [],
            "target": "new",
        }
        return action
