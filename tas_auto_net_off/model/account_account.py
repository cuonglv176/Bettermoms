# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _, _lt
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta
from itertools import chain
import io
from odoo.tools.misc import xlsxwriter
import pytz


class AccountAccount(models.Model):
    _inherit = 'account.account'

    bisexual_account = fields.Boolean(string='Tài khoản lưỡng tính', default=False)
    contra_account = fields.Many2one('account.account', string='Tài khoản đối ứng', default=False)
    compute_base_on = fields.Selection([
        ('du_ben_co', 'Dư bên có'),
        ('du_ben_no', 'Dư bên nợ'),
    ], string='Tính toán dựa trên', default=False)