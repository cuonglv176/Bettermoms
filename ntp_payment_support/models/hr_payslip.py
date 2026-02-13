import json
from odoo import models, fields, api
from ..utils.const import hash_content_to_puid


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    transfer_content_dict = fields.Text()
    transfer_content = fields.Char(
        "Transfer Content",
        help="Message that will be delivered to customer through bank transfer",
        tracking=True,
    )
    puid = fields.Char(
        "Payment Unique Id",
        help="Payment Unique Identifier is embeded into transfer content",
        store=True,
        tracking=True,
        compute="_compute_puid",
    )

    @api.depends("transfer_content")
    def _compute_puid(self):
        for rec in self:
            rec.puid = hash_content_to_puid(rec, rec.transfer_content)

    def action_generate_transfer_content(self):
        rec = self.env["ntp.transfer.content.generate.wizard"].create(
            {
                "template_type": "payslip",
                "model": "hr.payslip",
                "record_ids": json.dumps(self.ids),
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

    def action_download_transfer_for_payslip(self):
        data = json.dumps(
            {
                "model_ids": self.ids,
                "model": self._name,
            }
        )
        download_id = (
            self.env["ntp.transfer.content.export.wizard"]
            .sudo()
            .create(
                {
                    "data": data,
                    "export_type": "payslip",
                }
            )
        )
        download_id.filename = f"bulk_transfer_download_payslip_{download_id.id}.xlsx"
        download_id._compute_url()

        return {
            "type": "ir.actions.act_window",
            "name": "Download",
            "res_model": "ntp.transfer.content.export.wizard",
            "res_id": download_id.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
        }
