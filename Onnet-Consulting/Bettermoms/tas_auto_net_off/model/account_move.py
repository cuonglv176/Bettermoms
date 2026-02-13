# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import json
from datetime import datetime


class AccountMove(models.Model):
    _inherit = "account.move"

    move_netoff_id = fields.Many2one('account.move.netoff', string='Netoff')


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_netoff = fields.Boolean(string='Is Netoff?', default=False)
