import base64
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
from ..api.mst_finder import get_finder


def build_table_result(data_list: list):
    template = """
        <style>
            .styled-table {
                border-collapse: collapse;
                margin: 25px 0;
                font-family: sans-serif;
                min-width: 400px;
                width: 100%;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            }
            .styled-table thead tr {
                background-color: #009879;
                color: #ffffff;
                text-align: left;
            }
            .styled-table th, .styled-table td {
                padding: 3px 10px;
            }
            .styled-table tbody tr {
                border-bottom: 1px solid #dddddd;
            }

            .styled-table tbody tr:nth-of-type(even) {
                background-color: #f3f3f3;
            }

            .styled-table tbody tr:last-of-type {
                border-bottom: 2px solid #009879;
            }
        </style>

        <table class="styled-table">
        <thead>
            <tr>
                <td>Infomation</td>
                <td>Value</td>
            </tr>
        </thead>
        <tbody>
    """
    for vn, en, v in data_list:
        data = f"""
        <tr>
            <td title="{en}">{vn}</td>
            <td>{v}</td>
        </tr>
        """.strip()
        template += data
    template += "</tbody></table>"
    return template


class InvoiceViettelValidateConfirm(models.TransientModel):
    _name = "mst.vn.finder.wizard"
    _description = "MST VN Finder"

    user_id = fields.Many2one("res.users", "User")
    finder_type = fields.Selection(
        [
            ("idividual", "Individual"),
            ("company", "Company"),
        ],
        "MST Search For",
        default="company",
    )
    partner_id = fields.Many2one("res.partner", "Partner")
    tax_code = fields.Char("Tax Code")
    search_result = fields.Text("Search Result")
    search_result_html = fields.Text("Search Result Html")
    search_result_pdf = fields.Binary("Pdf Convert", attachment=True)
    search_captcha = fields.Image("Captcha Image")
    search_captcha_url = fields.Char("Captcha Url")
    search_captcha_code = fields.Char("Input Captcha")
    update_name = fields.Boolean("Update Name", default=True)

    def button_refresh_captcha(self):
        finder = get_finder(self.user_id.id, self.finder_type)
        image_url, image_data = finder.get_captcha()
        return {
            "type": "ir.actions.act_window",
            "name": "Find MST Information",
            "res_model": self._name,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_user_id": self.user_id.id,
                "default_tax_code": self.tax_code,
                "default_finder_type": self.finder_type,
                "default_search_captcha": base64.b64encode(image_data),
                "default_search_captcha_url": image_url,
            },
        }

    def button_find(self):
        finder = get_finder(self.user_id.id, self.finder_type)
        try:
            (
                search_result,
                search_result_html,
                search_result_pdf,
            ) = finder.get_mst_detail(self.tax_code, self.search_captcha_code)
        except Exception as e:
            raise UserError(f"cannot find MST data - error: {e}")
        image_url, image_data = finder.get_captcha()
        self.search_result = json.dumps(search_result)
        self.search_result_html = build_table_result(search_result)
        self.search_result_pdf = base64.b64encode(search_result_pdf)
        self.search_captcha_url = image_url
        self.search_captcha = base64.b64encode(image_data)
        self._cr.commit()
        return {
            "type": "ir.actions.act_window",
            "name": "Find MST Information",
            "res_model": self._name,
            "res_id": self.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            # "context": {
            #     "default_partner_id": self.partner_id.id,
            #     "default_user_id": self.user_id.id,
            #     "default_tax_code": self.tax_code,
            #     "default_finder_type": self.finder_type,
            #     "default_search_result": json.dumps(search_result),
            #     "default_search_result_html": build_table_result(search_result),
            #     "default_search_captcha": base64.b64encode(image_data),
            #     "default_search_captcha_url": image_url,
            #     "default_search_result_pdf": base64.b64encode(search_result_pdf)
            #     # "default_search_captcha_code": self.search_captcha_code
            # },
        }

    def button_save(self):
        date = fields.Datetime.now().strftime("%Y%m%d-%H%M%S")
        file_name = f"result-{date}.pdf"
        ir_attachment_id = self.env["ir.attachment"].create(
            {
                "name": file_name,
                "type": "binary",
                "datas": self.search_result_pdf,
                "store_fname": file_name,
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
            }
        )

        search_result = json.loads(self.search_result)
        result_dict = {k: v for _, k, v in search_result}

        # find invoice address related to this partner to update
        data = {
            "name": "{}".format(result_dict["legal_name"]),
            "type": "invoice",
            "street": result_dict["office_address"],
            "comment": f"Last Updated On: {date}",
        }
        self.partner_id.update(
            {
                "legal_name": result_dict["legal_name"],
                "street": result_dict["office_address"]
            }
        )

        updated = False
        for child in self.partner_id.child_ids:
            data_invoice = data.copy()
            if child.name == data_invoice['name']:
                child.update(data_invoice)
                updated = True
        if not updated:
            data_invoice = data.copy()
            data_invoice.update({"parent_id": self.partner_id.id})
            self.env["res.partner"].create(data_invoice)
        if self.update_name:
            self.partner_id.name = result_dict["trade_name"]
            self.partner_id.legal_name = result_dict["legal_name"]
