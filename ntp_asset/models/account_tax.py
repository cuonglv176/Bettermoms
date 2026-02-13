# __author__ = 'BinhTT'
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class NTPAccountTax(models.Model):
    _inherit = 'account.tax'

    sum_create_asset = fields.Boolean(string="""Sum Amount when create Expense""")
