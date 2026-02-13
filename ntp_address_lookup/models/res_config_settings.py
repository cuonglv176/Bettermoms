# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    address_lookup_online_search = fields.Boolean(
        "Enable Online Address Search",
        help="Use provinces.open-api.vn for online address search (free, no API key needed).",
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        try:
            get_param = self.env["ir.config_parameter"].sudo().get_param
            res.update(
                address_lookup_online_search=get_param(
                    "ntp_address_lookup.online_search", default="False"
                ) == "True",
            )
        except Exception as e:
            logger.error("Error reading address lookup config: %s", e)
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        try:
            set_param = self.env["ir.config_parameter"].sudo().set_param
            set_param(
                "ntp_address_lookup.online_search",
                str(self.address_lookup_online_search),
            )
            logger.info(
                "Address lookup online search set to: %s",
                self.address_lookup_online_search,
            )
        except Exception as e:
            logger.error("Error saving address lookup config: %s", e)
            raise
