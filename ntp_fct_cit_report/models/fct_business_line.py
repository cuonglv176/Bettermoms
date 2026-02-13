# __author__ = 'BinhTT'
from docutils.nodes import field

from odoo import models, fields

class FCTVendorbusiness(models.Model):
    _name = 'fct.business.line'

    name = fields.Char("Name")
    code = fields.Char("Code")


class FCTProducttemplate(models.Model):
    _inherit = 'product.template'

    fct_business = fields.Many2one('fct.business.line', 'VN FCT Business Code')