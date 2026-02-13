# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import json
from datetime import datetime


class AccountMove(models.Model):
    _inherit = "account.move"

    move_transfer_id = fields.Many2one('account.move.transfer', string='Transfer')


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_transfer = fields.Boolean(string='Is Transferred?', default=False)
