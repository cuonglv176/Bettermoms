# __author__ = 'BinhTT'
from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'
    amount = fields.Float(digits=(16, 9))