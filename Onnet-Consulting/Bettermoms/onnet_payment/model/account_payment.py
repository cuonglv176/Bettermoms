# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model_create_multi
    def create(self, vals_list):
        payment = super(AccountPayment, self).create(vals_list)
        payment.move_id.action_create_ma_phieu()
        return payment
