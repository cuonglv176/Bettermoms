import json
from odoo import api, models, fields, tools, _


class InvoiceViettelValidateConfirm(models.TransientModel):
    _name = "mst.vn.finder.wizard.address.confirm"
    _inherit = "mst.vn.finder.wizard"

    einvoice_id = fields.Many2one("ntp.einvoice", "EInvoice")
    einvoice_buyer_name = fields.Char(related="einvoice_id.buyer_name")
    einvoice_buyer_company_name = fields.Char(related="einvoice_id.buyer_company_name")
    einvoice_buyer_tax_code = fields.Char(related="einvoice_id.buyer_tax_code")
    einvoice_buyer_address = fields.Char(related="einvoice_id.buyer_address")
    note = fields.Text("Notes", compute="_compute_note")

    def button_confirm_address(self):
        self.einvoice_id.x_invoice_address_confirm = True

    def button_find(self):
        action = super().button_find()
        action["view_id"] = self.env.ref(
            "ntp_einvoice.mst_vn_finder_wizard_view_address_confirm"
        ).id
        return action

    def _compute_note(self):
        for rec in self:
            note = ["<b>Please manually checking following information:</b><br/>"]
            if rec.search_result:
                try:
                    search_result = json.loads(rec.search_result)
                    result_dict = {k: v for _, k, v in search_result}
                    if result_dict["legal_name"].strip() != rec.einvoice_id.buyer_company_name.strip():
                        note.append("<span style='color: red'>Buyer Company Name not match !!!!</span><br/>")
                        note.append(f"- From Tax: {result_dict['legal_name']}<br/>")
                        note.append(f"- From EInvoice: {rec.einvoice_id.buyer_company_name}<br/>")
                    else:
                        note.append("<span style='color: green'>Buyer Company Name matched</span><br/>")
                    if result_dict["office_address"].strip() != rec.einvoice_id.buyer_address.strip():
                        note.append("<span style='color: red'>Buyer Address not match !!!!</span><br/>")
                        note.append(f"- From Tax: {result_dict['office_address']}<br/>")
                        note.append(f"- From EInvoice: {rec.einvoice_id.buyer_address}<br/>")
                    else:
                        note.append("<span style='color: green'>Buyer Address matched</span><br/>")
                except Exception as e:
                    note.append(f"Error When Compare Address: {e}<br/>")
            rec.note = ''.join(note)
