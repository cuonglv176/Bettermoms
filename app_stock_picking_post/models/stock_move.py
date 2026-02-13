# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

from odoo.tools.float_utils import float_compare, float_round, float_is_zero

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def write(self, vals):
        if self.env.context.get('update_date_done', False) and self.picking_id and self.picking_id.date_done:
            vals['date'] = self.picking_id.date_done
        res = super(StockMove, self).write(vals)
        return res
