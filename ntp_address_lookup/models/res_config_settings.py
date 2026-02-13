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
    address_lookup_ai_suggest = fields.Boolean(
        "Enable AI Address Suggestion",
        help="Use OpenAI API to parse and suggest addresses when fuzzy matching fails.",
    )
    address_lookup_openai_api_key = fields.Char(
        "OpenAI API Key",
        help="API key for OpenAI (or compatible) service. "
             "Leave empty to use OPENAI_API_KEY environment variable.",
    )
    address_lookup_openai_base_url = fields.Char(
        "OpenAI Base URL",
        help="Custom base URL for OpenAI-compatible API. "
             "Leave empty for default OpenAI endpoint.",
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
                address_lookup_ai_suggest=get_param(
                    "ntp_address_lookup.ai_suggest_enabled", default="False"
                ) == "True",
                address_lookup_openai_api_key=get_param(
                    "ntp_address_lookup.openai_api_key", default=""
                ),
                address_lookup_openai_base_url=get_param(
                    "ntp_address_lookup.openai_base_url", default=""
                ),
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
            set_param(
                "ntp_address_lookup.ai_suggest_enabled",
                str(self.address_lookup_ai_suggest),
            )
            set_param(
                "ntp_address_lookup.openai_api_key",
                self.address_lookup_openai_api_key or "",
            )
            set_param(
                "ntp_address_lookup.openai_base_url",
                self.address_lookup_openai_base_url or "",
            )
            logger.info(
                "Address lookup settings saved: online_search=%s, ai_suggest=%s",
                self.address_lookup_online_search,
                self.address_lookup_ai_suggest,
            )
        except Exception as e:
            logger.error("Error saving address lookup config: %s", e)
            raise
