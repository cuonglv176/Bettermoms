# -*- coding: utf-8 -*-

from ast import literal_eval

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def write(self, vals):
        vals_date_done = fields.Datetime.to_datetime(vals.get('date_done'))
        if self.date_done and vals_date_done:
            if (self.date_done - vals_date_done).total_seconds()/3600 > 1 or vals_date_done > self.date_done:
                vals.update({'date_done': self.date_done})
                self.move_lines.with_context(update_date_done=True).write({'date': self.date_done})
        res = super(StockPicking, self).write(vals)
        return res
