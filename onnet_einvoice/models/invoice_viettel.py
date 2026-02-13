# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _

from odoo.exceptions import UserError


class InvoiceViettel(models.Model):
    _inherit = "invoice.viettel"
    _description = 'Invoice Viettel'

    street_partner = fields.Char("Street Partner", compute='_compute_street_partner', store=True,
                                 related=False)

    @api.depends('account_move_ids', 'account_move_ids.amount_untaxed_signed', 'account_move_ids.invoice_address')
    def _compute_street_partner(self):
        for inv in self:
            name = ''
            for move in inv.account_move_ids:
                if move.amount_untaxed_signed > 0 and move.invoice_address:
                    name = move.invoice_address
                    break
            inv.street_partner = name
