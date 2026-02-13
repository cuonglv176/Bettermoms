# -*- coding: utf-8 -*-

import datetime
from odoo import api, fields, models, _


class CompanyBranch(models.Model):
    _name = "company.branch"
    _description = "Branch of Company"

    name = fields.Char(string="Branch Name")
    code = fields.Char(string="Code")
    partner_id = fields.Many2one("res.partner", string="Related partner")
    vsi_domain = fields.Char(string="API Domain")
    business_service_domain = fields.Char(string="Business Service Domain")
    portal_service_domain = fields.Char(string="Portal Service Domain")
    vsi_tin = fields.Char(string="Mã số thuế", required=True)
    vsi_username = fields.Char(string="Username", required=True)
    vsi_password = fields.Char(string="Password", required=True)
    account = fields.Char(string="Account")
    password = fields.Char(string="Password")
    swap = fields.Boolean(string="Swap CusName/Buyer", default=False)
    vsi_template = fields.Char(string="Ký hiệu mẫu hóa đơn")
    vsi_template_type = fields.Char(string="Mã loại hóa đơn.")
    vsi_series = fields.Char(
        string="Ký hiệu hóa đơn",
        help="Đối với hóa đơn có nhiều dải thì dữ liệu invoiceSeries là yêu cầu bắt buộc",
    )
    vsi_version = fields.Selection(
        [
            ("v1", "Version 1 (Invoice Created Before 28/02/2022)"),
            ("v2", "Version 2 (Invoice Created After 28/02/2022)"),
        ],
        default='v1'
    )
    vsi_auto_pull = fields.Boolean("Auto Pull Invoice", default=False)
    vsi_invoice_pull_start_date = fields.Date("Pull Start Date", default=datetime.datetime.strptime("1970-01-01", "%Y-%m-%d").date())
