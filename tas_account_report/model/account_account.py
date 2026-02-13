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

    cashflow_credit = fields.Char('Cashflow item credit')
    cashflow_debit = fields.Char('Cashflow item debit')