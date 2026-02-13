import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..api import EInvoiceFactory


class EInvoicePreview(models.TransientModel):
    _name = "ntp.einvoice.preview"
    _description = "Preview EInvoice Before Create It"

    einvoice_id = fields.Many2one("ntp.einvoice", "EInvoice")
    einvoice_template_id = fields.Many2one("ntp.einvoice.template", "EInvoice Template")
    x_provider_preview = fields.Binary("Preview")

    def button_preview(self):
        factory = EInvoiceFactory.from_provider(self.einvoice_template_id)
        try:
            response, x_provider_preview = factory.get_preview_einvoice(self.einvoice_id)
        except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
            raise UserError(str(e))

        if not x_provider_preview:
            raise UserError(
                f"""
Cannot get preview invoice from provider server, May be you need to wait some secs and try again.
Response from server:

{response.text}
            """.strip()
            )
        self.x_provider_preview = x_provider_preview["file_data"]
        self._cr.commit()
        return {
            "type": "ir.actions.act_window",
            "name": "Preview EInvoice Before Create It",
            "res_model": "ntp.einvoice.preview",
            "res_id": self.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            # "context": {
            #     "default_einvoice_id": self.einvoice_id.id,
            #     "default_einvoice_template_id": self.einvoice_template_id.id,
            #     "default_x_provider_preview": x_provider_preview["file_data"],
            # },
        }
