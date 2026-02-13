# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountAccount(models.Model):
    _inherit = "account.account"

    is_default_3387 = fields.Boolean("Default 3387 Account", default=False)
    is_default_5113 = fields.Boolean("Default 5113 Account", default=False)
