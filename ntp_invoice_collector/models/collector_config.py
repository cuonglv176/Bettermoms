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

    # ---- Computed fields ----
    invoice_count = fields.Integer(
        "Invoice Count",
        compute="_compute_invoice_count",
    )
    log_count = fields.Integer(
        "Log Count",
        compute="_compute_log_count",
    )

    def _compute_invoice_count(self):
        for rec in self:
            try:
                rec.invoice_count = self.env["ntp.collected.invoice"].search_count(
                    [("config_id", "=", rec.id)]
                )
            except Exception:
                rec.invoice_count = 0

    def _compute_log_count(self):
        for rec in self:
            try:
                rec.log_count = self.env["ntp.collector.log"].search_count(
                    [("config_id", "=", rec.id)]
                )
            except Exception:
                rec.log_count = 0

    def action_view_invoices(self):
        """Open collected invoices for this config."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Collected Invoices - %s" % self.name,
            "res_model": "ntp.collected.invoice",
            "view_mode": "tree,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id, "default_provider": self.provider},
        }

    def action_view_logs(self):
        """Open collector logs for this config."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Collector Logs - %s" % self.name,
            "res_model": "ntp.collector.log",
            "view_mode": "tree,form",
            "domain": [("config_id", "=", self.id)],
        }

    def action_test_connection(self):
        """Test the API connection with current credentials."""
        self.ensure_one()
        if not self.api_url:
            raise UserError("Please configure the API Base URL first.")

        _logger.info(
            "Testing %s connection for config '%s'...",
            self.provider, self.name,
        )
        start_time = time.time()

        try:
            if self.provider == "shopee":
                self._test_shopee_connection()
            elif self.provider == "grab":
                self._test_grab_connection()
            else:
                raise UserError("Unknown provider: %s" % self.provider)

            duration = time.time() - start_time
            _logger.info(
                "Connection test successful for '%s' (%.2fs)",
                self.name, duration,
            )

            # Log success
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="test_connection",
                success=True,
                duration_seconds=duration,
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Connection Test",
                    "message": "Connection successful! (%.1fs)" % duration,
                    "type": "success",
                    "sticky": False,
                },
            }
        except UserError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            _logger.error(
                "Connection test failed for '%s': %s",
                self.name, e, exc_info=True,
            )
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="test_connection",
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
            raise UserError("Connection failed: %s" % str(e))

    def action_fetch_now(self):
        """Manually trigger invoice fetch for this config."""
        self.ensure_one()
        _logger.info(
            "Manual fetch triggered for config '%s' (%s)",
            self.name, self.provider,
        )

        inv_model = self.env["ntp.collected.invoice"]
        start_time = time.time()

        try:
            if self.provider == "shopee":
                count = inv_model._fetch_shopee_invoices(self)
            elif self.provider == "grab":
                count = inv_model._fetch_grab_invoices(self)
            else:
                raise UserError("Unknown provider: %s" % self.provider)

            duration = time.time() - start_time
            self.last_sync_date = fields.Datetime.now()

            _logger.info(
                "Manual fetch completed for '%s': %d invoices (%.1fs)",
                self.name, count, duration,
            )

            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="fetch",
                success=True,
                records_processed=count,
                duration_seconds=duration,
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Fetch Complete",
                    "message": "Fetched %d new invoice(s) from %s (%.1fs)." % (
                        count, self.name, duration,
                    ),
                    "type": "success",
                    "sticky": False,
                },
            }
        except UserError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            _logger.error(
                "Fetch failed for config '%s': %s",
                self.name, e, exc_info=True,
            )
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="fetch",
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
            raise UserError("Fetch failed: %s" % str(e))

    def _test_shopee_connection(self):
        """Test Shopee Open API connectivity."""
        base_url = (self.api_url or "").rstrip("/")
        if not base_url:
            raise UserError("Shopee API Base URL is not configured.")

        path = "/api/v2/shop/get_shop_info"
        timestamp = int(time.time())
        partner_id = int(self.api_key or 0)
        shop_id = int(self.shop_id or 0)

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

        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            if data.get("error"):
                raise UserError(
                    "Shopee API error: %s - %s"
                    % (data.get("error"), data.get("message", ""))
                )
            _logger.info("Shopee connection test passed for shop_id=%s", shop_id)
        except requests.RequestException as e:
            _logger.error("Shopee connection test failed: %s", e)
            raise UserError("Shopee connection error: %s" % str(e))

    def _test_grab_connection(self):
        """Test Grab API connectivity."""
        base_url = (self.api_url or "").rstrip("/")
        if not base_url:
            raise UserError("Grab API Base URL is not configured.")

        headers = {
            "Authorization": "Bearer %s" % (self.access_token or self.api_key or ""),
            "Content-Type": "application/json",
        }
        url = "%s/grabid/v1/oauth2/userinfo" % base_url

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                raise UserError(
                    "Grab API error (HTTP %d): %s"
                    % (response.status_code, response.text[:500])
                )
            _logger.info("Grab connection test passed")
        except requests.RequestException as e:
            _logger.error("Grab connection test failed: %s", e)
            raise UserError("Grab connection error: %s" % str(e))
