import base64
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..api import EInvoiceFactory
from ..utils.const import PROVIDER_EINVOICE_STATUS_REQUESTED


class EInvoiceManualSetInvoiceNo(models.TransientModel):
    _name = "ntp.einvoice.manual.set.invoice.no"
    _description = "Manual Set E-Invoice Number"

    einvoice_no = fields.Char("EInvoice No")
    einvoice_id = fields.Many2one("ntp.einvoice", "EInvoice")
    einvoice_template_id = fields.Many2one("ntp.einvoice.template", "EInvoice Template")
    x_provider_preview = fields.Binary("Preview")
    x_provider_find_msg = fields.Char("Auto Search Result")

    def button_preview(self):
        factory = EInvoiceFactory.from_provider(self.einvoice_template_id)
        x_provider_preview = None
        try:
            previous_einvoice_name = self.einvoice_id.name
            self.einvoice_id.name = self.einvoice_no
            x_provider_preview = factory.get_invoice_attachment_pdf(self.einvoice_id)
        finally:
            self.einvoice_id.name = previous_einvoice_name
        if not x_provider_preview:
            raise UserError(
                f"""Cannot get invoice from provider server, May be you need to wait some secs and try again.""".strip()
            )
        self.x_provider_preview = x_provider_preview["file_data"]
        self._cr.commit()
        return {
            "type": "ir.actions.act_window",
            "name": "Preview EInvoice Before Create It",
            "res_model": "ntp.einvoice.manual.set.invoice.no",
            "res_id": self.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
        }

    def button_set_invoice(self):
        # check the duplicate
        if self.env["ntp.einvoice"].sudo().search([("name", "=", self.einvoice_no)]):
            raise UserError("Your input invoice number is existed in system")
        if not self.x_provider_preview:
            raise UserError("Please check by clicking 'Preview' first")
        self.einvoice_id.name = self.einvoice_no
        self.einvoice_id.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_REQUESTED

    def button_try_to_find_invoice_no(self):
        factory = EInvoiceFactory.from_provider(self.einvoice_template_id)
        try:
            if self.einvoice_id.x_provider_data:
                invoice = factory.search_invoice_by_x_provider_data(self.einvoice_id)
                if invoice:
                    self.einvoice_no = invoice.invoice_no
                    self.x_provider_find_msg = f"We found this invoice may match {invoice.invoice_no}, created on {invoice.issue_date}, preview to see !!!"
        except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
            raise UserError(str(e))
        except:
            pass
