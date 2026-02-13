# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)



class AccountAccountTemplate(models.Model):
    _inherit = 'account.account.template'

    level = fields.Integer("Level")
    sequence = fields.Integer("Sequence")
    type = fields.Selection([('chitiet', 'Chi tiết'),('view', 'View')])
    parent_id = fields.Many2one('account.account.template')


class AccountAccount(models.Model):
    _inherit = "account.account"

    level = fields.Integer("Level")
    sequence = fields.Integer("Sequence")
    type = fields.Selection([('chitiet', 'Chi tiết'),('view', 'View')], string="View Type")
    parent_id = fields.Many2one('account.account')
