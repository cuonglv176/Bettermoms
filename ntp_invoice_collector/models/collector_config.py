# -*- coding: utf-8 -*-

import logging
import hashlib
import hmac
import time

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CollectorConfig(models.Model):
    _name = "ntp.collector.config"
    _description = "Marketplace Invoice Collector Configuration"
    _order = "name"

    name = fields.Char("Configuration Name", required=True)
    provider = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("grab", "Grab"),
        ],
        string="Provider",
        required=True,
    )
    api_url = fields.Char(
        "API Base URL",
        help="Base URL for the marketplace API.",
    )
    api_key = fields.Char(
        "API Key / App Key",
        help="Application Key or Partner ID for API authentication.",
    )
    api_secret = fields.Char(
        "API Secret / Partner Key",
        help="Secret key used for HMAC signing or token generation.",
    )
    shop_id = fields.Char(
        "Shop ID / Account ID",
        help="The shop or account identifier on the marketplace.",
    )
    access_token = fields.Char(
        "Access Token",
        help="OAuth access token (if applicable).",
    )
    is_active = fields.Boolean("Active", default=True)
    last_sync_date = fields.Datetime(
        "Last Sync Date",
        readonly=True,
        help="Timestamp of the last successful invoice sync.",
    )
    sync_interval_hours = fields.Integer(
        "Sync Interval (hours)",
        default=24,
        help="How often to auto-fetch invoices (used by cron job).",
    )
    notes = fields.Text("Notes")

    def action_test_connection(self):
        """Test the API connection with current credentials."""
        self.ensure_one()
        if not self.api_url:
            raise UserError("Please configure the API Base URL first.")

        try:
            if self.provider == "shopee":
                self._test_shopee_connection()
            elif self.provider == "grab":
                self._test_grab_connection()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Connection Test",
                    "message": "Connection successful!",
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            raise UserError("Connection failed: %s" % str(e))

    def action_fetch_now(self):
        """Manually trigger invoice fetch for this config."""
        self.ensure_one()
        inv_model = self.env["ntp.collected.invoice"]
        try:
            if self.provider == "shopee":
                count = inv_model._fetch_shopee_invoices(self)
            elif self.provider == "grab":
                count = inv_model._fetch_grab_invoices(self)
            else:
                count = 0
            self.last_sync_date = fields.Datetime.now()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Fetch Complete",
                    "message": "Fetched %d new invoice(s) from %s." % (count, self.name),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            _logger.error("Fetch failed for config %s: %s", self.name, e, exc_info=True)
            raise UserError("Fetch failed: %s" % str(e))

    def _test_shopee_connection(self):
        """Test Shopee Open API connectivity."""
        # Shopee Open Platform uses HMAC-SHA256 signing
        # This is a basic connectivity test
        base_url = self.api_url.rstrip("/")
        path = "/api/v2/shop/get_shop_info"
        timestamp = int(time.time())
        partner_id = int(self.api_key or 0)
        shop_id = int(self.shop_id or 0)

        # Build sign string: partner_id + path + timestamp + access_token + shop_id
        sign_base = "%d%s%d%s%d" % (
            partner_id, path, timestamp,
            self.access_token or "", shop_id,
        )
        sign = hmac.new(
            (self.api_secret or "").encode("utf-8"),
            sign_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        url = "%s%s" % (base_url, path)
        params = {
            "partner_id": partner_id,
            "timestamp": timestamp,
            "access_token": self.access_token or "",
            "shop_id": shop_id,
            "sign": sign,
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if data.get("error"):
            raise UserError(
                "Shopee API error: %s - %s"
                % (data.get("error"), data.get("message", ""))
            )

    def _test_grab_connection(self):
        """Test Grab API connectivity."""
        base_url = self.api_url.rstrip("/")
        headers = {
            "Authorization": "Bearer %s" % (self.access_token or self.api_key or ""),
            "Content-Type": "application/json",
        }
        # Basic health-check or profile endpoint
        url = "%s/grabid/v1/oauth2/userinfo" % base_url
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise UserError(
                "Grab API error (HTTP %d): %s"
                % (response.status_code, response.text[:500])
            )
