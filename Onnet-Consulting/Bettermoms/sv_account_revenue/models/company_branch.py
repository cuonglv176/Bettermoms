# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CompanyBranch(models.Model):
    _name = 'company.branch'
    _description = 'Branch of Company'

    name = fields.Char(string='Branch')
    code = fields.Char(string='Code')
    vsi_domain = fields.Char(string="API Domain")
    business_service_domain = fields.Char(string="Business Service Domain")
    portal_service_domain = fields.Char(string="Portal Service Domain")
    vsi_tin = fields.Char(string="Mã số thuế")
    vsi_username = fields.Char(string="Username")
    vsi_password = fields.Char(string="Password")
    account = fields.Char(string="Account")
    acpass = fields.Char(string="ACpass")
    swap = fields.Boolean(string="Swap CusName/Buyer", default=False)
    vsi_template = fields.Char(string="Mẫu Hóa Đơn")
    vsi_series = fields.Char(string="Ký hiệu hóa đơn")
