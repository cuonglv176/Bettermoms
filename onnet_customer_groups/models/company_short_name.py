# __author__ = 'BinhTT'
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CompanyShortName(models.Model):
    _name = "company.short.name"
    _rec_name = 'name'

    name = fields.Char("Short Name")

    @api.constrains('name')
    def check_name(self):
        if len(self.search([('name', '=', self.name)])) > 1:
            raise ValidationError('Code is existed!!')

