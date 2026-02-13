from odoo import api, models, fields
from odoo.exceptions import UserError


class Company(models.Model):
    _inherit = "res.company"

    einvoice_legal_name = fields.Char("Legal Name")
    einvoice_address = fields.Char("Invoice Address")
    einvoice_bank = fields.Char("Bank Name")
    einvoice_bank_account = fields.Char("Bank Account")
    einvoice_email = fields.Char("Email")
    einvoice_website = fields.Char("Website")
    einvoice_phone_number = fields.Char("Phone Number")
    einvoice_template_ids = fields.One2many("ntp.einvoice.template", "company_id")
