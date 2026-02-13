
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResUserBank(models.Model):
    _inherit = "res.partner.bank"

    einvoice_bank = fields.Boolean('Einvoice Bank')

    @api.constrains('einvoice_bank')
    def _check_partner_unique_einvoice_bank(self):
        partner_bank_einvoice = self.env['res.partner.bank'].search([('partner_id', '=', self.partner_id.id)])
        print('print partner_bank_einvoice', partner_bank_einvoice)
        if self.einvoice_bank and len(partner_bank_einvoice):
            raise ValidationError(
                _("Only Einvoice Bank = TRUE for 1 res.partner(%(partner)s)", partner=self.partner_id.name))
