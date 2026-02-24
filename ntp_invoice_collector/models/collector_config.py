# -*- coding: utf-8 -*-
"""
Invoice Collector Configuration
=================================
Stores API credentials and settings for each marketplace integration.

Supported providers:
  - Shopee: Open Platform API (HMAC-SHA256 signed)
  - Grab: E-invoice portal (vn.einvoice.grab.com) — session-based with auto CAPTCHA
"""

import json
import logging
import hashlib
import hmac
import time
from datetime import timedelta

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
        help=(
            "For Shopee: https://partner.shopeemobile.com\n"
            "For Grab: https://vn.einvoice.grab.com (default)"
        ),
    )
    api_key = fields.Char(
        "API Key / Username",
        help=(
            "For Shopee: Partner ID (numeric).\n"
            "For Grab: Portal username (Tài khoản đăng nhập)."
        ),
    )
    api_secret = fields.Char(
        "API Secret / Password",
        help=(
            "For Shopee: Partner Key for HMAC signing.\n"
            "For Grab: Portal password (Mật khẩu đăng nhập)."
        ),
    )
    shop_id = fields.Char(
        "Shop ID",
        help="For Shopee: the numeric Shop ID. Not used for Grab.",
    )
    access_token = fields.Char(
        "Access Token",
        help="For Shopee: OAuth access token. Not used for Grab.",
    )

    # ---- Grab-specific fields ----
    grab_captcha_image = fields.Binary(
        "CAPTCHA Image",
        attachment=False,
        help="Current CAPTCHA challenge image (temporary).",
    )
    grab_captcha_answer = fields.Char(
        "CAPTCHA Answer",
        help="Enter the text shown in the CAPTCHA image.",
    )
    grab_session_cookie = fields.Char(
        "Session Cookie",
        help="Stored .ASPXAUTH session cookie (auto-managed).",
    )
    grab_session_valid_until = fields.Datetime(
        "Session Valid Until",
        help="Estimated expiry time of the current Grab session.",
    )
    grab_login_status = fields.Selection(
        [
            ("not_logged_in", "Not Logged In"),
            ("captcha_pending", "CAPTCHA Required"),
            ("logged_in", "Logged In"),
            ("session_expired", "Session Expired"),
            ("error", "Login Error"),
        ],
        string="Login Status",
        default="not_logged_in",
        readonly=True,
    )
    grab_date_from = fields.Date(
        "Fetch From Date",
        help="Start date for fetching invoices. Defaults to last sync or 30 days ago.",
    )
    grab_use_auto_captcha = fields.Boolean(
        "Auto-Solve CAPTCHA",
        default=True,
        help=(
            "Use OpenAI Vision API to automatically solve CAPTCHA. "
            "Requires OPENAI_API_KEY environment variable or the field below."
        ),
    )
    grab_openai_api_key = fields.Char(
        "OpenAI API Key (Optional)",
        help=(
            "Optional: OpenAI API key for auto-solving CAPTCHA. "
            "If blank, uses the OPENAI_API_KEY environment variable."
        ),
    )

    # ---- Common fields ----
    is_active = fields.Boolean("Active", default=True)
    last_sync_date = fields.Datetime(
        "Last Sync Date",
        readonly=True,
    )
    sync_interval_hours = fields.Integer(
        "Sync Interval (hours)",
        default=24,
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
    grab_session_active = fields.Boolean(
        "Session Active",
        compute="_compute_grab_session_active",
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

    def _compute_grab_session_active(self):
        for rec in self:
            if rec.provider != "grab":
                rec.grab_session_active = False
                continue
            if (
                rec.grab_login_status == "logged_in"
                and rec.grab_session_valid_until
                and rec.grab_session_valid_until > fields.Datetime.now()
            ):
                rec.grab_session_active = True
            else:
                rec.grab_session_active = False

    # ====================================================================
    # Smart Button Actions
    # ====================================================================

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Collected Invoices - %s" % self.name,
            "res_model": "ntp.collected.invoice",
            "view_mode": "tree,form",
            "domain": [("config_id", "=", self.id)],
            "context": {
                "default_config_id": self.id,
                "default_provider": self.provider,
            },
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Collector Logs - %s" % self.name,
            "res_model": "ntp.collector.log",
            "view_mode": "tree,form",
            "domain": [("config_id", "=", self.id)],
        }

    # ====================================================================
    # Test Connection
    # ====================================================================

    def action_test_connection(self):
        """Test the API connection with current credentials."""
        self.ensure_one()
        _logger.info("Testing %s connection for '%s'...", self.provider, self.name)
        start_time = time.time()

        try:
            if self.provider == "shopee":
                if not self.api_url:
                    raise UserError("Please configure the API Base URL first.")
                self._test_shopee_connection()
            elif self.provider == "grab":
                self._test_grab_portal_connection()
            else:
                raise UserError("Unknown provider: %s" % self.provider)

            duration = time.time() - start_time
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
            _logger.error("Connection test failed for '%s': %s", self.name, e, exc_info=True)
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="test_connection",
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
            raise UserError("Connection failed: %s" % str(e))

    # ====================================================================
    # Fetch Now (Manual Trigger)
    # ====================================================================

    def action_fetch_now(self):
        """Manually trigger invoice fetch for this config."""
        self.ensure_one()
        _logger.info("Manual fetch triggered for '%s' (%s)", self.name, self.provider)

        inv_model = self.env["ntp.collected.invoice"]
        start_time = time.time()

        try:
            if self.provider == "shopee":
                count = inv_model._fetch_shopee_invoices(self)
            elif self.provider == "grab":
                count = inv_model._fetch_grab_portal_invoices(self)
            else:
                raise UserError("Unknown provider: %s" % self.provider)

            duration = time.time() - start_time
            self.last_sync_date = fields.Datetime.now()

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
            _logger.error("Fetch failed for '%s': %s", self.name, e, exc_info=True)
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="fetch",
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
            raise UserError("Fetch failed: %s" % str(e))

    # ====================================================================
    # Grab Portal: Auto Fetch (CAPTCHA solved automatically)
    # ====================================================================

    def action_grab_auto_fetch(self):
        """
        Fully automatic Grab invoice fetch:
        1. Load login page
        2. Auto-solve CAPTCHA with OpenAI Vision API
        3. Login
        4. Fetch invoices
        """
        self.ensure_one()
        if self.provider != "grab":
            raise UserError("This action is only for Grab configurations.")
        if not self.api_key:
            raise UserError("Please configure the Username (API Key field) for Grab.")
        if not self.api_secret:
            raise UserError("Please configure the Password (API Secret field) for Grab.")

        from .grab_session import GrabEInvoiceSession

        base_url = (self.api_url or "").rstrip("/") or "https://vn.einvoice.grab.com"
        inv_model = self.env["ntp.collected.invoice"]
        start_time = time.time()

        try:
            session = GrabEInvoiceSession(
                username=self.api_key,
                password=self.api_secret,
                base_url=base_url,
            )

            # Try auto-login with CAPTCHA solving
            openai_key = self.grab_openai_api_key or None
            login_ok = session.auto_login(openai_api_key=openai_key, max_attempts=5)

            if not login_ok:
                error_detail = session.last_error or "Unknown error"
                is_locked = session.is_account_locked

                self.write({"grab_login_status": "error"})

                if is_locked:
                    raise UserError(
                        "⚠️ Grab account is LOCKED!\n\n"
                        "Your account '%s' has been locked due to too many "
                        "failed login attempts.\n\n"
                        "Please contact Grab support to unlock your account "
                        "before trying again.\n\n"
                        "Detail: %s" % (self.api_key, error_detail)
                    )

                raise UserError(
                    "Grab auto-login failed after 5 attempts.\n\n"
                    "Possible causes:\n"
                    "- Wrong username or password\n"
                    "- Account locked (too many failed attempts)\n"
                    "- CAPTCHA recognition errors\n"
                    "- Network issues\n\n"
                    "Detail: %s\n\n"
                    "Try: Load CAPTCHA manually and enter it yourself." % error_detail
                )

            # Store session cookie
            aspx_cookie = session._session.cookies.get(".ASPXAUTH")
            self.write({
                "grab_login_status": "logged_in",
                "grab_session_cookie": aspx_cookie or "",
                "grab_session_valid_until": fields.Datetime.now() + timedelta(minutes=25),
                "grab_captcha_image": False,
                "grab_captcha_answer": "",
            })

            # Fetch invoices
            count = inv_model._fetch_grab_portal_invoices_with_session(self, session)

            duration = time.time() - start_time
            self.last_sync_date = fields.Datetime.now()

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
                    "title": "Auto Fetch Complete",
                    "message": (
                        "Auto-login successful! Fetched %d new invoice(s) "
                        "from Grab (%.1fs)." % (count, duration)
                    ),
                    "type": "success",
                    "sticky": False,
                },
            }

        except UserError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            _logger.error("Grab auto-fetch failed for '%s': %s", self.name, e, exc_info=True)
            self.write({"grab_login_status": "error"})
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="fetch",
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
            raise UserError("Auto-fetch failed: %s" % str(e))

    # ====================================================================
    # Grab Portal: Manual CAPTCHA Flow (2-step)
    # ====================================================================

    def action_grab_prepare_login(self):
        """Step 1: Load CAPTCHA image for manual entry."""
        self.ensure_one()
        if self.provider != "grab":
            raise UserError("This action is only for Grab configurations.")
        if not self.api_key:
            raise UserError("Please configure the Username (API Key field).")
        if not self.api_secret:
            raise UserError("Please configure the Password (API Secret field).")

        from .grab_session import GrabEInvoiceSession

        base_url = (self.api_url or "").rstrip("/") or "https://vn.einvoice.grab.com"

        try:
            session = GrabEInvoiceSession(
                username=self.api_key,
                password=self.api_secret,
                base_url=base_url,
            )
            session.prepare_login()
            captcha_b64 = session.get_captcha_image_b64()

            if not captcha_b64:
                raise UserError(
                    "Could not fetch CAPTCHA image. Check network connectivity."
                )

            # Store session state temporarily
            param_key = "ntp_invoice_collector.grab_csrf_%d" % self.id
            self.env["ir.config_parameter"].sudo().set_param(
                param_key, session._csrf_token or ""
            )
            cookies_dict = {c.name: c.value for c in session._session.cookies}
            cookie_key = "ntp_invoice_collector.grab_cookies_%d" % self.id
            self.env["ir.config_parameter"].sudo().set_param(
                cookie_key, json.dumps(cookies_dict)
            )

            self.write({
                "grab_captcha_image": captcha_b64,
                "grab_captcha_answer": "",
                "grab_login_status": "captcha_pending",
            })

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "CAPTCHA Ready",
                    "message": "Enter the CAPTCHA code and click 'Login & Fetch'.",
                    "type": "info",
                    "sticky": True,
                },
            }

        except UserError:
            raise
        except Exception as e:
            _logger.error("CAPTCHA load failed for '%s': %s", self.name, e, exc_info=True)
            self.write({"grab_login_status": "error"})
            raise UserError("Failed to load CAPTCHA: %s" % str(e))

    def action_grab_login_and_fetch(self):
        """Step 2: Submit CAPTCHA answer, login, and fetch invoices."""
        self.ensure_one()
        if self.provider != "grab":
            raise UserError("This action is only for Grab configurations.")
        if not self.grab_captcha_answer:
            raise UserError("Please enter the CAPTCHA answer first.")

        inv_model = self.env["ntp.collected.invoice"]
        start_time = time.time()

        try:
            count = inv_model._fetch_grab_portal_invoices(
                self, captcha_answer=self.grab_captcha_answer
            )
            duration = time.time() - start_time
            self.write({
                "last_sync_date": fields.Datetime.now(),
                "grab_captcha_image": False,
                "grab_captcha_answer": "",
                "grab_login_status": "logged_in",
            })

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
                    "message": "Fetched %d new invoice(s) from Grab (%.1fs)." % (
                        count, duration,
                    ),
                    "type": "success",
                    "sticky": False,
                },
            }

        except UserError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            _logger.error("Grab login & fetch failed: %s", e, exc_info=True)
            self.write({"grab_login_status": "error"})
            self.env["ntp.collector.log"].log_operation(
                config=self,
                operation="fetch",
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )
            raise UserError("Login & Fetch failed: %s" % str(e))

    def action_grab_refresh_captcha(self):
        """Refresh the CAPTCHA image."""
        return self.action_grab_prepare_login()

    # ====================================================================
    # Connection Test Methods
    # ====================================================================

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
        except requests.RequestException as e:
            raise UserError("Shopee connection error: %s" % str(e))

    def _test_grab_portal_connection(self):
        """Test Grab e-invoice portal connectivity."""
        base_url = (self.api_url or "").rstrip("/") or "https://vn.einvoice.grab.com"

        if not self.api_key:
            raise UserError("Grab Username is not configured.")
        if not self.api_secret:
            raise UserError("Grab Password is not configured.")

        try:
            response = requests.get(
                "%s/tai-khoan/dang-nhap" % base_url,
                timeout=15,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
                    ),
                },
            )
            if response.status_code == 200 and "Đăng nhập" in response.text:
                _logger.info("Grab portal connection test passed")
            else:
                raise UserError(
                    "Grab portal returned unexpected response (HTTP %d)."
                    % response.status_code
                )
        except requests.RequestException as e:
            raise UserError("Grab portal connection error: %s" % str(e))
