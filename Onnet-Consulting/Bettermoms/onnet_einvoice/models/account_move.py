# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _

from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_address = fields.Char('Invoice Address', related=False)

    @api.onchange('partner_id')
    def _onchange_partner_id_invoice_address1(self):
        if self.partner_id:
            self.invoice_address = self.partner_id.street or ''

    @api.onchange('invoice_address')
    def _onchange_invoice_address(self):
        if self.invoice_address:
            self.invoice_address = self.invoice_address or ''

    def btn_update_street(self):
        # Function update street by partner
        if self.partner_id:
            self.invoice_address = self.partner_id.street or ''
        # Function call wizard to update invoice_address
        # view_id = self.env.ref('onnet_einvoice.wizard_update_move_street_form_view').id
        # return {'type': 'ir.actions.act_window',
        #         'name': _('Update Street'),
        #         'res_model': 'wizard.update.move.street',
        #         'target': 'new',
        #         'view_mode': 'form',
        #         'views': [[view_id, 'form']],
        #         }
