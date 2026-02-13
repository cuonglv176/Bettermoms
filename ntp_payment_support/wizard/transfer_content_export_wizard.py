import base64
import json
from collections import OrderedDict
import re
from urllib.parse import urljoin
from odoo import tools, models, api, fields
from odoo.exceptions import UserError
import pandas as pd
from io import BytesIO
from ..utils.normalize import normalize_string


class AccountPaymentBulkTransferDownload(models.TransientModel):
    _name = "ntp.transfer.content.export.wizard"

    data = fields.Text()
    export_type = fields.Selection(
        [
            ("payment", "Payment"),
            ("payslip", "Payslip"),
        ]
    )
    export_format = fields.Selection(
        [("shinhan10", "Shinhan Excel Format (Update 2022May17)")],
        "Template Format",
        default="shinhan10",
    )
    transfer_status = fields.Selection(
        [
            ("prepare", "Prepare"),
            ("transferring", "Transferring"),
            # ("transferred", "Paid"),
        ],
        string="Transfer Status",
    )
    # set_payment_post = fields.Boolean("Set Payment Post")
    attachment_id = fields.Many2one("ir.attachment")
    filename = fields.Char("Download Filename", default="bulk_transfer_download.xlsx")
    # config = fields.Many2one("ntp.transfer.content.export.template")
    url = fields.Char("Url", compute="_compute_url")

    @api.onchange("filename")
    def onchange_filename(self):
        self._compute_url()

    def _compute_url(self):
        for rec in self:
            _field = "attachment_id"
            self.url = urljoin(
                self[0].get_base_url(),
                f"/web/ntp_payment_support/download_bulk_transfer?model={self._name}&field={_field}&filename={self.filename}&id={self.id}",
            )

    def action_generate_report(self):
        func = getattr(self, f"_{self.export_format}_action_generate_report")
        func()

    def _shinhan10_action_generate_report(self):
        self.ensure_one()
        swift_code = "SHBKVNVXXXX"
        banks = (
            self.env["res.bank"]
            .sudo()
            .search(["|", ("bic", "=", swift_code), ("bic", "=", swift_code.lower())])
        )
        citad_codes = []
        if banks:
            for bank in banks:
                citad_codes += bank.bank_branch_ids.mapped("citad_code")

        if self.attachment_id:
            self.sudo().attachment_id.unlink()
        data = json.loads(self.data)
        model_ids = self.env[data["model"]].sudo().browse(data["model_ids"])
        columns = OrderedDict(
            {
                "benificiary_account": "Beneficiary Account No.",
                "transfer_amount": "Transfer Amount",
                "bank_code": "Bank Code",
                "benificiary_name_1": "Beneficiary Customer Name 1",
                "benificiary_name_2": "Beneficiary Customer Name 2",
                "payment_detail_1": "Payment Details 1",
                "payment_detail_2": "Payment Details 2",
                "payment_detail_3": "Payment Details 3",
                "payment_detail_4": "Payment Details 4",
                "payment_detail_5": "Payment Details 5",
                "payment_detail_6": "Payment Details 6",
                "tax_code": "Tax Code",
                "tax_reference": "Tax Reference",
            }
        )

        data_rows_raw = []

        for rec in model_ids:
            # re overload template generate to check if we need update on bank account
            # and other info if user change it
            row = json.loads(rec.transfer_content_dict)
            if "template_id" in row:
                template_id = row["template_id"]
                if template_id:
                    template = self.env["ntp.transfer.content.template"].browse(
                        template_id
                    )
                    content_dict = template.action_generate_content(rec)
                    if not rec.transfer_content:
                        rec.transfer_content = content_dict["transfer_content"]
                    rec.transfer_content_dict = json.dumps(content_dict)

        for rec in model_ids:
            row = {}
            data = json.loads(rec.transfer_content_dict)
            row = data
            benificiary_name = row.pop("benificiary_name")
            transfer_content = row.pop("transfer_content")
            if "template_id" in row:
                template_id = row.pop("template_id")
            if not rec.transfer_content:
                rec.transfer_content = normalize_string(transfer_content)
            transfer_content = rec.transfer_content
            # TODO: stupid assume that payment name is existed in transfer content
            # TODO: when export
            # if re.match("^[a-zA-Z0-9]", transfer_content):
            #     transfer_content = rec.puid + " " + transfer_content
            # else:
            #     transfer_content = rec.puid + transfer_content
            row["benificiary_name_1"] = benificiary_name[0:35]
            row["benificiary_name_2"] = benificiary_name[35:]
            if row["bank_code"] in citad_codes:
                row["bank_code"] = "99999999"
            keys = [
                "payment_detail_1",
                "payment_detail_2",
                "payment_detail_3",
                "payment_detail_4",
                "payment_detail_5",
                "payment_detail_6",
            ]

            for _id, k in enumerate(keys):
                row[k] = transfer_content[_id * 35 : (_id + 1) * 35]
            data_rows_raw.append(row)

        data_rows = []
        for row in data_rows_raw:
            row_dict = {v: "" for k, v in columns.items()}
            row_data = {columns[k]: v for k, v in row.items()}
            row_dict.update(row_data)
            data_rows.append(row_dict)

        file = BytesIO()
        df = pd.DataFrame(data_rows)
        df.to_excel(file, engine="xlsxwriter", index=False)
        datas = base64.b64encode(file.getbuffer())
        attachment_id = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": f"bulk_transfer_download_{self.id}.xlsx",
                    "type": "binary",
                    "datas": datas,
                    "store_fname": f"bulk_transfer_download_{self.id}.xlsx",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )
        self.attachment_id = attachment_id
        if not self.filename:
            self.filename = f"bulk_transfer_download_{self.id}.xlsx"

    def button_download(self):
        self.action_generate_report()
        return {"type": "ir.actions.act_url", "url": self.url, "target": "current"}

    def button_set_payment_post(self):
        data = json.loads(self.data)
        model_ids = self.env[data["model"]].sudo().browse(data["model_ids"])

        if data["model"] == "account.payment":
            for rec in model_ids:
                if rec.state == "draft":
                    rec.action_post()
        action = {
            "name": "Download",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "ntp.transfer.content.export.wizard",
            "views": [[False, "form"]],
            "context": {},
            "res_id": self.id,
            "domain": [],
            "target": "new",
        }
        return action

    def button_set_payment_status(self):
        data = json.loads(self.data)
        model_ids = self.env[data["model"]].sudo().browse(data["model_ids"])

        if data["model"] == "account.payment":
            _map = {
                "prepare": ["prepare", "transferring"],
                "transferring": ["prepare", "transferring"],
            }
            for rec in model_ids:
                try:
                    if self.transfer_status in _map[rec.transfer_status]:
                        rec.transfer_status = self.transfer_status
                    else:
                        raise UserError(
                            f"Payment {rec.name}: cannot set status from {rec.transfer_status} -> {self.transfer_status}"
                        )
                except:
                    raise UserError(
                        f"Payment {rec.name}: cannot set status from {rec.transfer_status} -> {self.transfer_status}"
                    )
        action = {
            "name": "Download",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "ntp.transfer.content.export.wizard",
            "views": [[False, "form"]],
            "context": {},
            "res_id": self.id,
            "domain": [],
            "target": "new",
        }
        return action
