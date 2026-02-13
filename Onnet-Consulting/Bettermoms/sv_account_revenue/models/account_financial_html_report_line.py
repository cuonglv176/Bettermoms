# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.tools.misc import format_date


class AccountFinanciaHtmlReportLine(models.Model):
    _inherit = 'account.financial.html.report.line'

    code_report = fields.Char("Mã báo cáo tài chính")
