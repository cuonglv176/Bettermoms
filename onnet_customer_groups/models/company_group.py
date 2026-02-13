# __author__ = 'BinhTT'
from odoo import models, fields, api
from odoo.exceptions import ValidationError
class CompanyGroup(models.Model):
    _name = 'company.group'
    name = fields.Char('Code')

    @api.constrains('name')
    def check_name(self):
        if len(self.search([('name', '=', self.name)])) > 1:
            raise ValidationError('Code is existed!!')