# __author__ = 'BinhTT'
from odoo import fields, models, api

class AccountTaxTag(models.Model):
    _inherit = 'account.account.tag'
    vat_type = fields.Many2one('vat.type', 'VAT Type')
    account_id = fields.Many2one('account.account', 'Account')
    product_id = fields.Many2one('product.product', 'Product')
    # is_landed_costs_line = fields.Boolean('Auto Tick when create Tax Bill')
class VatType(models.Model):
    _name = 'vat.type'
    name = fields.Char('Name')