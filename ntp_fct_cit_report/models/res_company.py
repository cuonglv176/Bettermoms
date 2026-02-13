# __author__ = 'BinhTT'

from odoo import models, fields, api, _

class FCTResCompany(models.Model):
    _inherit = "res.company"

    fct_code = fields.Char('FCT Code')