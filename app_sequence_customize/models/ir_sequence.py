# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta, date as datetime_date
from dateutil.relativedelta import relativedelta
# import calendar


class IrSequence(models.Model):
    _inherit = 'ir.sequence'
    _order = 'code,id desc'

    # 增加翻译，注意，增加翻译后不要用 name 排序
    name = fields.Char(required=True, translate=True)
    # 注意，原生的序号，使用的不是utc，是使用者的时间，即 now = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
    # 默认是 year 模式
    reset_interval = fields.Selection([
        ('daily', 'Reset Daily'),
        ('weekly', 'Reset Weekly'),
        ('monthly', 'Reset Monthly'),
        ('yearly', 'Reset Yearly(Default)')], string='Reset Frequency', default='monthly',
        help='Once you change the Frequency, you must remove the exist date range under.')

    # 注意，此处处理是当utc时区

    # 注意，这个tz按增加的用户处理，故无须跟公司关联，直接单独计算
    # 时区不需要，odoo原生就是按使用者的时区，故要注意如果是多公司的特殊处理
    # tz = fields.Selection(_tz_get, string='Reset on Timezone', default=lambda self: self._context.get('tz'),
    #                       help="The sequence's timezone to base on.")
    # tz_offset = fields.Char(compute='_compute_tz_offset', string='Timezone offset', invisible=True)

    def _compute_date_from_to(self, date):
        self.ensure_one()
        date_from = date_to = fields.Date.from_string(date)
        if self.reset_interval == 'weekly':
            date_from = date_from - timedelta(days=date_from.weekday())
            date_to = date_from + timedelta(days=6)
        elif self.reset_interval == 'monthly':
            date_from = datetime_date(date_from.year, date_from.month, 1)
            date_to = date_from + relativedelta(months=1)
            date_to += relativedelta(days=-1)
        elif self.reset_interval == 'yearly':
            date_from = datetime_date(date_from.year, 1, 1)
            date_to = datetime_date(date_from.year, 12, 31)
        return date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')

    def _create_date_range_seq(self, date):
        self.ensure_one()
        if not self.reset_interval:
            return super()._create_date_range_seq(date)
        date_from, date_to = self._compute_date_from_to(date)

        # 此处查找原来的设定。注意有可能 from 和 to 有一项为空，故要两种排序来找
        date_range = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '>=', date), ('date_from', '<=', date_to)],
                                                               order='date_from desc', limit=1)
        if date_range:
            date_to = date_range.date_from + timedelta(days=-1)
        date_range = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_to', '>=', date_from), ('date_to', '<=', date)],
                                                               order='date_to desc', limit=1)
        if date_range:
            date_from = date_range.date_to + timedelta(days=1)

        seq_date_range = self.env['ir.sequence.date_range'].sudo().create({
            'date_from': date_from,
            'date_to': date_to,
            'sequence_id': self.id,
        })
        return seq_date_range
