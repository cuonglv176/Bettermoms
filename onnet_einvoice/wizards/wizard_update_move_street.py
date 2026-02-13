# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class WizardUpdateMoveStreet(models.TransientModel):
    _name = 'wizard.update.move.street'
    _description = 'Wizard Update Move Street'

    def _get_default_partner_id(self):
        partner_id = False
        active_id = self._context.get('active_id', False)
        if active_id:
            partner_id = active_id
        return partner_id

    street = fields.Char(string='Street', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True,
                                 default=_get_default_partner_id, )

    def btn_update_street(self):
        move_obj = self.env['account.move']
        active_id = self._context.get('active_id', False)
        if active_id:
            move = move_obj.browse(active_id)
            move.write({
                'invoice_address': self.street or '',
            })
        return True
