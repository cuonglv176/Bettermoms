import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..api import EInvoiceFactory


class EInvoiceSendMail(models.TransientModel):
    _name = "ntp.einvoice.send.email"
    _description = "Send EInvoice Email To Customer"

    einvoice_id = fields.Many2one("ntp.einvoice", "EInvoice")
    einvoice_template_id = fields.Many2one(
        "ntp.einvoice.template", related="einvoice_id.einvoice_template_id"
    )
    partner_id = fields.Many2one("res.partner", related="einvoice_id.partner_id")
    invoice_address = fields.Many2one(
        "res.partner",
        domain="['|', ('id', '=', partner_id), '&', ('type', '=', 'invoice'), ('parent_id', '=', partner_id)]",
        help="You will need to update email in invoice address to able to send email",
    )
    email_address = fields.Char(
        "Customer Email Address", related="invoice_address.email"
    )
    cc_email_address = fields.Char(
        "Cc Email Address", help="Alternate email address to send"
    )

    def button_send_email(self):
        factory = EInvoiceFactory.from_provider(self.einvoice_template_id)
        emails = []
        if self.email_address:
            emails.append(self.email_address)
        if self.cc_email_address:
            emails.append(self.cc_email_address)

        if not emails:
            raise UserError("At least 1 email address is required")
        try:
            responses = factory.send_email(self.einvoice_id, email_addresses=emails)
        except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
            raise UserError(str(e))

        msg = ["Send Email Results:"]
        for email, resp in zip(emails, responses):
            code = resp.status_code
            json = resp.json()
            status = "SUCCEEDED" if code == 200 else "FAILED"
            msg.append(f"- [{status}] {email}: return code {code} , {json}")
        self.einvoice_id.message_post(body="<br/>".join(msg))
