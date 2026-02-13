from odoo import models, api, fields, _
from datetime import datetime, date


class interest_rate(models.Model):
    _name = "interest.rate"
    _rec_name = 'date'

    date = fields.Date('Date')
    rate = fields.Float('Rate')

