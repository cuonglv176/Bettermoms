# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import Counter

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_compare, float_is_zero
import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def write(self, vals):
        if self.picking_id and self.picking_id.date_done:
            vals['date'] = self.picking_id.date_done
        res = super(StockMoveLine, self).write(vals)
        return res
