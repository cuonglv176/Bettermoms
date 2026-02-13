# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_revenue_journal = fields.Boolean("Is Revenue Journal", default=False)
