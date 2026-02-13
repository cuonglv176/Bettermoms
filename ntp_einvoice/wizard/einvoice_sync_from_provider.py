from odoo import api, models, fields, _
from ..api import EInvoiceFactory
from ..utils.const import *


class EInvoiceSyncFromProvider(models.TransientModel):
    _name = "ntp.einvoice.sync.from.provider"
    _description = "Sync Invoice Data From Provider"

    einvoice_id = fields.Many2one("ntp.einvoice")
    update_provider_einvoice_status = fields.Boolean("EInvoice Status", default=True)
    update_payment_status = fields.Boolean("Payment Status", default=True)
    update_attachment_data = fields.Selection(
        [
            ("no", "Do Not Update"),
            ("pdf", "Pdf"),
            ("xml", "Xml"),
            ("all", "All Available Attachments"),
        ],
        "Attachments",
        default="no",
    )
    update_detail_from_xml = fields.Boolean("Get From Xml", default=False)
    force_recreate_lines = fields.Boolean("Recreate EInvoice Lines", default=False)

    @api.onchange("update_detail_from_xml")
    def onchange_update_detail_from_xml(self):
        self.ensure_one()
        if self.update_detail_from_xml:
            if (
                self.update_attachment_data not in ["xml", "all"]
                and not self.einvoice_id.x_provider_xml_file
            ):
                self.update_attachment_data = "xml"

    def button_perform_update(self):
        return_action = None
        factory = EInvoiceFactory.from_provider(self.einvoice_id.einvoice_template_id)
        res_pdf = res_xml = None
        if self.update_attachment_data == "pdf":
            res_pdf = factory.get_invoice_attachment_pdf(self.einvoice_id)
        elif self.update_attachment_data == "xml":
            res_xml = factory.get_invoice_attachment_xml(self.einvoice_id)
        elif self.update_attachment_data == "all":
            res_pdf = factory.get_invoice_attachment_pdf(self.einvoice_id)
            res_xml = factory.get_invoice_attachment_xml(self.einvoice_id)

        if res_pdf:
            # delete all pdf with same name first
            self.env["ir.attachment"].search(
                [
                    ("res_model", "=", self.einvoice_id._name),
                    ("res_id", "=", self.einvoice_id.id),
                    ("name", "=", res_pdf["file_name"]),
                ]
            ).unlink()
            ir_attachment_id = self.env["ir.attachment"].create(
                {
                    "name": res_pdf["file_name"],
                    "type": "binary",
                    "datas": res_pdf["file_data"],
                    "store_fname": res_pdf["file_name"],
                    "res_model": self.einvoice_id._name,
                    "res_id": self.einvoice_id.id,
                }
            )
            return_action = {"type": "ir.actions.client", "tag": "reload"}

        if res_xml:
            # delete all xml with same name first
            self.env["ir.attachment"].search(
                [
                    ("res_model", "=", self.einvoice_id._name),
                    ("res_id", "=", self.einvoice_id.id),
                    ("name", "=", res_xml["file_name"]),
                ]
            ).unlink()
            ir_attachment_id = self.env["ir.attachment"].create(
                {
                    "name": res_xml["file_name"],
                    "type": "binary",
                    "datas": res_xml["file_data"],
                    "store_fname": res_xml["file_name"],
                    "res_model": self.einvoice_id._name,
                    "res_id": self.einvoice_id.id,
                }
            )

        if self.update_provider_einvoice_status:
            einvoice_status = factory.get_invoice_status(self.einvoice_id)
            if einvoice_status:
                self.einvoice_id.issue_date = einvoice_status["issue_date"]
                if self.einvoice_id.provider_einvoice_status not in [
                    PROVIDER_EINVOICE_STATUS_BE_ADJUSTED,
                    PROVIDER_EINVOICE_STATUS_BE_REPLACED,
                ]:
                    # this state is final, cannot be reversed so cannot change if falling into these state
                    self.einvoice_id.provider_einvoice_status = einvoice_status["status"]
            else:
                self.einvoice_id.message_post(body="Cannot get payment status from api")

        if self.update_payment_status:
            einvoice_payment_status = factory.get_invoice_payment_status(
                self.einvoice_id
            )
            if einvoice_payment_status:
                if einvoice_payment_status["payment_status"] == "paid":
                    self.einvoice_id.payment_status = PAYMENT_STATUS_PAID
                else:
                    self.einvoice_id.payment_status = PAYMENT_STATUS_NOT_PAID_YET
            else:
                self.einvoice_id.message_post(body="Cannot get payment status from api")

        if self.update_detail_from_xml:
            self.einvoice_id.button_update_detail_from_xml(self.force_recreate_lines)

        return return_action
