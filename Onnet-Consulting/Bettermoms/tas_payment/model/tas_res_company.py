# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ResCompany(models.Model):
    _inherit = 'res.company'

    manager = fields.Many2one("res.users",string="Tổng giám đốc")
    accountant = fields.Many2one("res.users",string="Kế toán trưởng")
    treasurer = fields.Many2one("res.users",string="Thủ quỹ")
