# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_open_collector_configs(self):
        """Open the collector configuration list view."""
        return {
            "type": "ir.actions.act_window",
            "name": "Marketplace Collector Configs",
            "res_model": "ntp.collector.config",
            "view_mode": "tree,form",
            "target": "current",
        }
