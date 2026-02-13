# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class RevenueRecognizeLog(models.Model):
    _name = 'revenue.recognize.log'
    _description = 'Logs of Revenue Recognition'

    name = fields.Char(string='uID')
    log_status = fields.Char(string='Log Status')
    traceback = fields.Text()
