# __author__ = 'BinhTT'
from odoo import models, api, fields

class NTPAccountAccount(models.Model):
    _inherit = 'account.account'

    cit_vat = fields.Float('CIT rate (FCT)')
    fct_vat = fields.Float('VAT rate (FCT)')


class NTPAccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    tax_type = fields.Selection([('normal', "Normal"),
                                 ('fct_vat', "FCT VAT"),
                                 ('fct_cit', "FCT CIT")], default='normal')
