# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import io
import json
import logging
import time
import zipfile
from datetime import datetime, timedelta

import requests
from urllib.parse import urljoin

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
REQUEST_TIMEOUT = 30


class CollectedInvoice(models.Model):
    _name = "ntp.collected.invoice"
    _description = "Collected Marketplace Invoice"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transaction_date desc, id desc"

    name = fields.Char(
        "Reference",
        required=True,
        index=True,
        copy=False,
        help="External invoice/order reference from the marketplace.",
    )
    provider = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("grab", "Grab"),
        ],
        string="Provider",
        required=True,
        tracking=True,
    )
    config_id = fields.Many2one(
        "ntp.collector.config",
        string="Source Config",
        ondelete="set null",
    )
    transaction_date = fields.Date("Transaction Date", tracking=True)
    external_order_id = fields.Char(
        "External Order ID",
        index=True,
        help="The marketplace order ID used for matching with Odoo sale orders.",
    )
    total_amount = fields.Float("Total Amount", digits=(16, 2))
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
    )

    # ---- Odoo Matching ----
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Matched Sale Order",
        ondelete="set null",
        tracking=True,
    )
    sale_order_amount = fields.Monetary(
        "SO Amount",
        related="sale_order_id.amount_total",
        readonly=True,
    )
    amount_match = fields.Boolean(
        "Amount Matched",
        compute="_compute_amount_match",
        store=True,
    )
    account_move_id = fields.Many2one(
        "account.move",
        string="Related Invoice/Bill",
        ondelete="set null",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
    )

    # ---- Bizzi Integration ----
    bizzi_invoice_id = fields.Char("Bizzi Invoice ID", tracking=True)
    bizzi_status = fields.Selection(
        [
            ("pending", "Pending Upload"),
            ("uploaded", "Uploaded to Bizzi"),
            ("verified", "Verified by Bizzi"),
            ("error", "Error"),
        ],
        string="Bizzi Status",
        default="pending",
        tracking=True,
    )

    # ---- Workflow State ----
    state = fields.Selection(
        [
            ("draft", "Fetched"),
            ("matched", "Matched with SO"),
            ("pushed", "Pushed to Bizzi"),
            ("verified", "Invoice Verified"),
            ("error", "Error"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    # ---- Retry tracking ----
    retry_count = fields.Integer(
        "Retry Count",
        default=0,
        help="Number of times this invoice has been retried.",
    )
    last_error_date = fields.Datetime(
        "Last Error Date",
        readonly=True,
    )

    # ---- Attachments & Notes ----
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Invoice Files",
        help="PDF/XML invoice files from the marketplace.",
    )
    notes = fields.Text("Notes")
    error_message = fields.Text("Error Details")

    _sql_constraints = [
        (
            "external_order_uniq",
            "UNIQUE(provider, external_order_id)",
            "This marketplace order has already been collected!",
        ),
    ]

    # ====================================================================
    # Computed Fields
    # ====================================================================

    @api.depends("total_amount", "sale_order_id", "sale_order_id.amount_total")
    def _compute_amount_match(self):
        for rec in self:
            if rec.sale_order_id and rec.total_amount:
                rec.amount_match = abs(
                    rec.total_amount - rec.sale_order_id.amount_total
                ) < 0.01
            else:
                rec.amount_match = False

    # ====================================================================
    # HTTP Request Helper with Retry
    # ====================================================================

    def _make_request(self, method, url, config=None, **kwargs):
        """Make an HTTP request with retry logic and logging.

        Args:
            method (str): HTTP method ('get' or 'post').
            url (str): Request URL.
            config: Optional collector config for logging.
            **kwargs: Additional arguments passed to requests.

        Returns:
            requests.Response: The response object.

        Raises:
            requests.RequestException: If all retries fail.
        """
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        log_model = self.env["ntp.collector.log"]
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            start_time = time.time()
            try:
                if method.lower() == "get":
                    response = requests.get(url, **kwargs)
                elif method.lower() == "post":
                    response = requests.post(url, **kwargs)
                else:
                    raise ValueError("Unsupported HTTP method: %s" % method)

                duration = time.time() - start_time

                _logger.debug(
                    "HTTP %s %s -> %d (%.2fs, attempt %d/%d)",
                    method.upper(), url[:100], response.status_code,
                    duration, attempt, MAX_RETRIES,
                )

                # Log successful request
                if response.status_code in (200, 201):
                    log_model.log_operation(
                        config=config,
                        operation="fetch",
                        success=True,
                        request_url=url[:500],
                        response_code=response.status_code,
                        duration_seconds=duration,
                    )
                    return response

                # Log non-success response
                _logger.warning(
                    "HTTP %s %s returned %d (attempt %d/%d): %s",
                    method.upper(), url[:100], response.status_code,
                    attempt, MAX_RETRIES, response.text[:200],
                )

                if response.status_code in (429, 500, 502, 503, 504):
                    # Retryable status codes
                    if attempt < MAX_RETRIES:
                        delay = RETRY_DELAY_SECONDS * attempt
                        _logger.info("Retrying in %ds...", delay)
                        time.sleep(delay)
                        continue

                # Non-retryable error or last attempt
                log_model.log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    request_url=url[:500],
                    response_code=response.status_code,
                    response_summary=response.text[:500],
                    duration_seconds=duration,
                    error_message="HTTP %d: %s" % (
                        response.status_code, response.text[:200],
                    ),
                )
                return response

            except requests.ConnectionError as e:
                last_exception = e
                duration = time.time() - start_time
                _logger.warning(
                    "Connection error for %s (attempt %d/%d): %s",
                    url[:100], attempt, MAX_RETRIES, e,
                )
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS * attempt
                    time.sleep(delay)
                    continue

            except requests.Timeout as e:
                last_exception = e
                duration = time.time() - start_time
                _logger.warning(
                    "Timeout for %s (attempt %d/%d): %s",
                    url[:100], attempt, MAX_RETRIES, e,
                )
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS * attempt
                    time.sleep(delay)
                    continue

            except requests.RequestException as e:
                last_exception = e
                duration = time.time() - start_time
                _logger.error(
                    "Request error for %s (attempt %d/%d): %s",
                    url[:100], attempt, MAX_RETRIES, e,
                )
                break

        # All retries exhausted
        log_model.log_operation(
            config=config,
            operation="fetch",
            success=False,
            request_url=url[:500],
            error_message="All %d retries failed: %s" % (MAX_RETRIES, str(last_exception)),
            duration_seconds=duration if 'duration' in dir() else 0,
        )
        raise last_exception or requests.RequestException(
            "All retries failed for %s" % url
        )

    # ====================================================================
    # Shopee HMAC Signing Helper
    # ====================================================================

    def _shopee_sign(self, config, path, timestamp=None):
        """Generate HMAC-SHA256 signature for Shopee API.

        Args:
            config: Collector config record.
            path (str): API path.
            timestamp (int): Unix timestamp (defaults to current time).

        Returns:
            tuple: (sign, timestamp, partner_id, shop_id)
        """
        if timestamp is None:
            timestamp = int(time.time())
        partner_id = int(config.api_key or 0)
        shop_id = int(config.shop_id or 0)

        sign_base = "%d%s%d%s%d" % (
            partner_id, path, timestamp,
            config.access_token or "", shop_id,
        )
        sign = hmac.new(
            (config.api_secret or "").encode("utf-8"),
            sign_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return sign, timestamp, partner_id, shop_id

    # ====================================================================
    # Cron Entry Points
    # ====================================================================

    @api.model
    def cron_fetch_invoices(self):
        """Scheduled action: fetch invoices from all active collector configs."""
        configs = self.env["ntp.collector.config"].search(
            [("is_active", "=", True)]
        )
        _logger.info(
            "Cron fetch invoices started: %d active configs found", len(configs),
        )
        total_fetched = 0
        total_errors = 0

        for config in configs:
            start_time = time.time()
            try:
                if config.provider == "shopee":
                    count = self._fetch_shopee_invoices(config)
                elif config.provider == "grab":
                    count = self._fetch_grab_portal_invoices(config)
                else:
                    _logger.warning(
                        "Unknown provider '%s' for config %s, skipping",
                        config.provider, config.name,
                    )
                    continue

                duration = time.time() - start_time
                config.last_sync_date = fields.Datetime.now()
                total_fetched += count

                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=True,
                    records_processed=count,
                    duration_seconds=duration,
                )

                _logger.info(
                    "Invoice fetch completed for config '%s': %d new invoices (%.1fs)",
                    config.name, count, duration,
                )
            except Exception as e:
                duration = time.time() - start_time
                total_errors += 1
                _logger.error(
                    "Invoice fetch error for '%s': %s",
                    config.name, e, exc_info=True,
                )
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message=str(e),
                    duration_seconds=duration,
                )

        _logger.info(
            "Cron fetch invoices completed: %d fetched, %d errors across %d configs",
            total_fetched, total_errors, len(configs),
        )

    @api.model
    def cron_push_to_bizzi(self):
        """Scheduled action: push pending invoices to Bizzi."""
        pending = self.search(
            [
                ("bizzi_status", "=", "pending"),
                ("state", "in", ["draft", "matched"]),
            ]
        )
        _logger.info(
            "Cron push to Bizzi started: %d pending invoices", len(pending),
        )
        pushed = 0
        errors = 0

        for inv in pending:
            try:
                inv._push_to_bizzi()
                pushed += 1
            except Exception as e:
                errors += 1
                inv.write({
                    "bizzi_status": "error",
                    "error_message": str(e)[:1000],
                    "last_error_date": fields.Datetime.now(),
                })
                _logger.error(
                    "Bizzi push error for %s: %s", inv.name, e, exc_info=True,
                )
                self.env["ntp.collector.log"].log_operation(
                    config=inv.config_id,
                    provider=inv.provider,
                    operation="push_bizzi",
                    invoice=inv,
                    success=False,
                    error_message=str(e),
                )

        _logger.info(
            "Cron push to Bizzi completed: %d pushed, %d errors", pushed, errors,
        )

    # ====================================================================
    # Provider Fetch Methods
    # ====================================================================

    def _fetch_shopee_invoices(self, config):
        """Fetch completed orders from Shopee Open Platform API.

        Uses the Order API (v2) to get orders completed since last sync.
        Returns the count of new invoices created.
        """
        count = 0
        base_url = (config.api_url or "").rstrip("/")
        if not base_url:
            raise UserError("Shopee API URL is not configured.")

        # Calculate time range
        now = int(time.time())
        if config.last_sync_date:
            time_from = int(config.last_sync_date.timestamp())
        else:
            # Default: last 30 days
            time_from = now - (30 * 24 * 3600)

        path = "/api/v2/order/get_order_list"
        sign, timestamp, partner_id, shop_id = self._shopee_sign(config, path)

        params = {
            "partner_id": partner_id,
            "timestamp": timestamp,
            "access_token": config.access_token or "",
            "shop_id": shop_id,
            "sign": sign,
            "time_range_field": "create_time",
            "time_from": time_from,
            "time_to": now,
            "page_size": 50,
            "order_status": "COMPLETED",
            "cursor": "",
        }

        has_more = True
        page = 0
        while has_more:
            page += 1
            try:
                url = "%s%s" % (base_url, path)
                response = self._make_request("get", url, config=config, params=params)
                data = response.json()

                if data.get("error"):
                    _logger.warning(
                        "Shopee API error (page %d): %s - %s",
                        page, data.get("error"), data.get("message"),
                    )
                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        operation="fetch",
                        success=False,
                        error_message="Shopee API: %s - %s" % (
                            data.get("error"), data.get("message"),
                        ),
                        request_url=url,
                    )
                    break

                resp = data.get("response", {})
                order_list = resp.get("order_list", [])

                _logger.info(
                    "Shopee fetch page %d: %d orders returned",
                    page, len(order_list),
                )

                for order in order_list:
                    order_sn = order.get("order_sn", "")
                    if not order_sn:
                        continue

                    # Skip if already collected
                    existing = self.search([
                        ("provider", "=", "shopee"),
                        ("external_order_id", "=", order_sn),
                    ], limit=1)
                    if existing:
                        continue

                    # Fetch order detail for amount
                    try:
                        detail = self._shopee_get_order_detail(
                            config, base_url, partner_id, shop_id, order_sn,
                        )
                    except Exception as e:
                        _logger.warning(
                            "Failed to get Shopee order detail for %s: %s",
                            order_sn, e,
                        )
                        detail = {"total_amount": 0.0}

                    vals = {
                        "name": "SHOPEE-%s" % order_sn,
                        "provider": "shopee",
                        "config_id": config.id,
                        "external_order_id": order_sn,
                        "transaction_date": datetime.fromtimestamp(
                            order.get("create_time", now)
                        ).date(),
                        "total_amount": detail.get("total_amount", 0.0),
                        "state": "draft",
                        "bizzi_status": "pending",
                    }
                    try:
                        self.sudo().create(vals)
                        count += 1
                    except Exception as e:
                        _logger.warning(
                            "Failed to create invoice for Shopee order %s: %s",
                            order_sn, e,
                        )

                # Pagination
                has_more = resp.get("more", False)
                if has_more:
                    params["cursor"] = resp.get("next_cursor", "")
                    # Re-sign for next page
                    sign, timestamp, _, _ = self._shopee_sign(config, path)
                    params["sign"] = sign
                    params["timestamp"] = timestamp
                else:
                    has_more = False

            except requests.RequestException as e:
                _logger.error("Shopee API request error (page %d): %s", page, e)
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message="Request error: %s" % str(e),
                )
                break

        # Auto-match after fetching
        if count > 0:
            try:
                self._auto_match_shopee_orders()
            except Exception as e:
                _logger.error("Auto-match error after Shopee fetch: %s", e)

        _logger.info(
            "Shopee fetch completed for config '%s': %d new invoices",
            config.name, count,
        )
        return count

    def _shopee_get_order_detail(self, config, base_url, partner_id, shop_id, order_sn):
        """Fetch single order detail from Shopee for amount info."""
        path = "/api/v2/order/get_order_detail"
        sign, timestamp, _, _ = self._shopee_sign(config, path)

        params = {
            "partner_id": partner_id,
            "timestamp": timestamp,
            "access_token": config.access_token or "",
            "shop_id": shop_id,
            "sign": sign,
            "order_sn_list": order_sn,
            "response_optional_fields": "order_income",
        }
        try:
            url = "%s%s" % (base_url, path)
            response = self._make_request("get", url, config=config, params=params)
            data = response.json()
            resp = data.get("response", {})
            orders = resp.get("order_list", [])
            if orders:
                order_income = orders[0].get("order_income", {})
                return {
                    "total_amount": order_income.get(
                        "escrow_amount", orders[0].get("total_amount", 0.0)
                    ),
                }
        except Exception as e:
            _logger.warning("Could not fetch Shopee order detail for %s: %s", order_sn, e)
        return {"total_amount": 0.0}

    def _fetch_grab_invoices(self, config):
        """
        Legacy method: kept for backward compatibility.
        Delegates to the new portal-based fetcher.
        """
        return self._fetch_grab_portal_invoices(config)

    def _fetch_grab_portal_invoices(self, config, captcha_answer=None):
        """
        Fetch invoices from the Grab e-invoice portal (vn.einvoice.grab.com).

        This method handles the full session-based authentication flow:
          1. Load the login page to obtain CSRF token and session cookie.
          2. Fetch the CAPTCHA image.
          3. Either use a provided captcha_answer or retrieve a stored one.
          4. Submit the login form.
          5. Paginate through the invoice list.
          6. Create ntp.collected.invoice records for new invoices.
          7. Optionally download PDF/XML attachments.

        When called from the cron job (captcha_answer=None), the method will
        check if a valid session cookie is stored in the config. If not, it
        will log a warning and skip the config (the user must manually trigger
        login via the config form).

        Args:
            config: ntp.collector.config record.
            captcha_answer (str): CAPTCHA text answer. If None, uses stored
                                  session cookie or raises an error.

        Returns:
            int: Number of new invoice records created.
        """
        from .grab_session import GrabEInvoiceSession

        count = 0
        base_url = (config.api_url or "").rstrip("/") or "https://vn.einvoice.grab.com"

        if not config.api_key:
            raise UserError(
                "Grab Username (API Key field) is not configured for '%s'." % config.name
            )
        if not config.api_secret:
            raise UserError(
                "Grab Password (API Secret field) is not configured for '%s'." % config.name
            )

        # ----------------------------------------------------------------
        # Build or restore session
        # ----------------------------------------------------------------
        session = GrabEInvoiceSession(
            username=config.api_key,
            password=config.api_secret,
            base_url=base_url,
        )

        if captcha_answer:
            # Full login flow: use stored CSRF token and cookies
            param_key = "ntp_invoice_collector.grab_csrf_%d" % config.id
            cookie_key = "ntp_invoice_collector.grab_cookies_%d" % config.id
            get_param = self.env["ir.config_parameter"].sudo().get_param

            csrf_token = get_param(param_key, default="")
            cookies_json = get_param(cookie_key, default="{}")

            if csrf_token:
                session._csrf_token = csrf_token
                try:
                    cookies_dict = json.loads(cookies_json)
                    for name, value in cookies_dict.items():
                        session._session.cookies.set(name, value)
                except Exception:
                    pass
            else:
                # No stored CSRF token; do a fresh prepare
                session.prepare_login()
                session.get_captcha_image()  # Needed to get CaptchaHash cookie

            _logger.info(
                "Attempting Grab portal login for config '%s'...", config.name
            )
            login_ok = session.login(captcha_answer)

            if not login_ok:
                config.write({"grab_login_status": "error"})
                raise UserError(
                    "Grab portal login failed for '%s'. "
                    "Please check your credentials and CAPTCHA answer." % config.name
                )

            config.write({"grab_login_status": "logged_in"})

        elif config.grab_session_cookie:
            # Restore session from stored cookie
            _logger.info(
                "Restoring Grab session from stored cookie for config '%s'",
                config.name,
            )
            session._session.cookies.set(".ASPXAUTH", config.grab_session_cookie)
            session._authenticated = True
            session._auth_time = datetime.now()

        else:
            # No session available — cron job cannot proceed without login
            _logger.warning(
                "Grab config '%s' has no active session. "
                "Please log in manually via the config form (CAPTCHA required).",
                config.name,
            )
            self.env["ntp.collector.log"].log_operation(
                config=config,
                operation="fetch",
                success=False,
                error_message=(
                    "No active Grab session. Log in manually via config form."
                ),
            )
            return 0

        # ----------------------------------------------------------------
        # Calculate date range
        # ----------------------------------------------------------------
        if config.grab_date_from:
            date_from_dt = config.grab_date_from
        elif config.last_sync_date:
            date_from_dt = config.last_sync_date.date()
        else:
            date_from_dt = (datetime.now() - timedelta(days=30)).date()

        date_to_dt = datetime.now().date()

        # Vietnamese date format: dd/MM/yyyy
        date_from_str = date_from_dt.strftime("%d/%m/%Y")
        date_to_str = date_to_dt.strftime("%d/%m/%Y")

        _logger.info(
            "Fetching Grab invoices for config '%s': %s to %s",
            config.name, date_from_str, date_to_str,
        )

        # ----------------------------------------------------------------
        # Paginate through invoice list
        # ----------------------------------------------------------------
        page = 1
        page_size = 50
        has_more = True
        total_fetched = 0

        while has_more:
            try:
                result = session.fetch_invoices(
                    date_from=date_from_str,
                    date_to=date_to_str,
                    page=page,
                    page_size=page_size,
                )
            except ValueError as e:
                # Session expired
                _logger.warning(
                    "Grab session expired for config '%s': %s", config.name, e
                )
                config.write({"grab_login_status": "session_expired"})
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message="Session expired: %s" % str(e),
                )
                break
            except Exception as e:
                _logger.error(
                    "Error fetching Grab invoices (page %d): %s", page, e
                )
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message="Fetch error (page %d): %s" % (page, str(e)),
                )
                break

            invoices = result.get("invoices", [])
            has_more = result.get("has_more", False)

            _logger.info(
                "Grab portal page %d: %d invoices returned (has_more=%s)",
                page, len(invoices), has_more,
            )

            if not invoices:
                break

            # ----------------------------------------------------------------
            # Process each invoice
            # ----------------------------------------------------------------
            new_invoice_ids = []  # For batch attachment download

            for inv_data in invoices:
                inv_id = inv_data.get("id", "")
                inv_number = inv_data.get("invoice_number", inv_id)

                if not inv_id and not inv_number:
                    continue

                external_id = str(inv_id or inv_number)

                # Skip if already collected
                existing = self.search([
                    ("provider", "=", "grab"),
                    ("external_order_id", "=", external_id),
                ], limit=1)
                if existing:
                    continue

                # Parse transaction date
                raw_date = inv_data.get("invoice_date", "")
                parsed_date = self._parse_grab_date(raw_date)

                vals = {
                    "name": "GRAB-%s" % (inv_number or external_id),
                    "provider": "grab",
                    "config_id": config.id,
                    "external_order_id": external_id,
                    "transaction_date": parsed_date,
                    "total_amount": float(inv_data.get("total_amount", 0) or 0),
                    "state": "draft",
                    "bizzi_status": "pending",
                    "notes": (
                        "Buyer: %s | Tax: %s | Seller: %s | Status: %s"
                        % (
                            inv_data.get("buyer_name", ""),
                            inv_data.get("buyer_tax_code", ""),
                            inv_data.get("seller_name", ""),
                            inv_data.get("status", ""),
                        )
                    ),
                }

                # Try to match partner by tax code
                buyer_tax = inv_data.get("buyer_tax_code", "")
                if buyer_tax:
                    partner = self.env["res.partner"].search(
                        [("vat", "=", buyer_tax)], limit=1
                    )
                    if partner:
                        vals["partner_id"] = partner.id

                try:
                    new_rec = self.sudo().create(vals)
                    count += 1
                    total_fetched += 1
                    new_invoice_ids.append((new_rec.id, external_id))

                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        provider="grab",
                        operation="fetch",
                        invoice=new_rec,
                        success=True,
                    )
                    _logger.debug(
                        "Created Grab invoice record: %s (ID: %s)",
                        vals["name"], external_id,
                    )

                except Exception as e:
                    _logger.warning(
                        "Failed to create Grab invoice record for %s: %s",
                        external_id, e,
                    )

            # ----------------------------------------------------------------
            # Download PDF/XML attachments for new invoices (batch)
            # ----------------------------------------------------------------
            if new_invoice_ids:
                try:
                    self._attach_grab_invoice_files(
                        session, config, new_invoice_ids
                    )
                except Exception as e:
                    _logger.warning(
                        "Could not download Grab invoice attachments: %s", e
                    )

            page += 1
            if page > 100:  # Safety limit
                _logger.warning("Grab fetch: reached page limit (100), stopping.")
                break

        # ----------------------------------------------------------------
        # Auto-match after fetching
        # ----------------------------------------------------------------
        if count > 0:
            try:
                self._auto_match_grab_orders()
            except Exception as e:
                _logger.error("Auto-match error after Grab fetch: %s", e)

        # Store .ASPXAUTH cookie for future cron runs
        aspx_cookie = session._session.cookies.get(".ASPXAUTH")
        if aspx_cookie:
            config.write({"grab_session_cookie": aspx_cookie})

        _logger.info(
            "Grab portal fetch completed for config '%s': %d new invoices",
            config.name, count,
        )
        return count

    def _parse_grab_date(self, raw_date):
        """
        Parse a date string from the Grab portal into an Odoo Date.

        The portal may return dates in various formats:
          - dd/MM/yyyy  (Vietnamese format)
          - yyyy-MM-dd  (ISO format)
          - dd-MM-yyyy

        Args:
            raw_date (str): Raw date string.

        Returns:
            date: Parsed date, or today's date on failure.
        """
        if not raw_date:
            return fields.Date.today()

        raw_date = str(raw_date).strip()

        # Try various formats
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw_date[:10], fmt).date()
            except ValueError:
                continue

        # Try ISO datetime
        try:
            return fields.Date.from_string(raw_date[:10])
        except Exception:
            pass

        _logger.warning("Could not parse Grab date: '%s'", raw_date)
        return fields.Date.today()

    def _attach_grab_invoice_files(self, session, config, invoice_id_pairs):
        """
        Download PDF/XML files for new Grab invoices and attach them to records.

        Args:
            session (GrabEInvoiceSession): Authenticated session.
            config: ntp.collector.config record.
            invoice_id_pairs (list): List of (odoo_record_id, external_grab_id) tuples.
        """
        if not invoice_id_pairs:
            return

        external_ids = [pair[1] for pair in invoice_id_pairs]
        odoo_id_map = {pair[1]: pair[0] for pair in invoice_id_pairs}

        _logger.info(
            "Downloading attachments for %d Grab invoices...", len(external_ids)
        )

        try:
            zip_content = session.download_invoice_files(
                invoice_ids=external_ids,
                allow_pdf=True,
                allow_xml=True,
            )
        except Exception as e:
            _logger.warning("Failed to download Grab invoice files: %s", e)
            return

        if not zip_content:
            _logger.info("No attachment data returned for Grab invoices.")
            return

        # Extract ZIP and attach files to corresponding records
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                for filename in zf.namelist():
                    file_data = zf.read(filename)
                    if not file_data:
                        continue

                    # Try to match filename to an invoice external ID
                    matched_odoo_id = None
                    for ext_id in external_ids:
                        if ext_id in filename:
                            matched_odoo_id = odoo_id_map.get(ext_id)
                            break

                    if not matched_odoo_id:
                        # Attach to first record as fallback
                        matched_odoo_id = invoice_id_pairs[0][0] if invoice_id_pairs else None

                    if matched_odoo_id:
                        try:
                            attachment = self.env["ir.attachment"].sudo().create({
                                "name": filename,
                                "datas": base64.b64encode(file_data).decode("utf-8"),
                                "res_model": "ntp.collected.invoice",
                                "res_id": matched_odoo_id,
                                "mimetype": (
                                    "application/pdf" if filename.lower().endswith(".pdf")
                                    else "application/xml" if filename.lower().endswith(".xml")
                                    else "application/octet-stream"
                                ),
                            })
                            # Link attachment to the invoice record
                            invoice_rec = self.browse(matched_odoo_id)
                            invoice_rec.sudo().write({
                                "attachment_ids": [(4, attachment.id)],
                            })
                            _logger.debug(
                                "Attached '%s' to Grab invoice record %d",
                                filename, matched_odoo_id,
                            )
                        except Exception as e:
                            _logger.warning(
                                "Failed to create attachment '%s': %s", filename, e
                            )

        except zipfile.BadZipFile:
            _logger.warning(
                "Downloaded Grab file is not a valid ZIP archive "
                "(size=%d bytes). Skipping attachment.",
                len(zip_content),
            )

    # ====================================================================
    # Auto-Matching
    # ====================================================================

    def _auto_match_shopee_orders(self):
        """Auto-match collected Shopee invoices with existing sale orders."""
        unmatched = self.search([
            ("provider", "=", "shopee"),
            ("sale_order_id", "=", False),
            ("external_order_id", "!=", False),
            ("state", "=", "draft"),
        ])
        matched_count = 0
        for inv in unmatched:
            try:
                so = self.env["sale.order"].search([
                    ("x_shopee_order_id", "=", inv.external_order_id),
                ], limit=1)
                if so:
                    inv.write({
                        "sale_order_id": so.id,
                        "partner_id": so.partner_id.id,
                        "state": "matched",
                    })
                    matched_count += 1
                    self.env["ntp.collector.log"].log_operation(
                        config=inv.config_id,
                        provider="shopee",
                        operation="match",
                        invoice=inv,
                        success=True,
                    )
            except Exception as e:
                _logger.warning(
                    "Auto-match error for invoice %s: %s", inv.name, e,
                )

        if matched_count:
            _logger.info(
                "Auto-matched %d Shopee invoices with sale orders", matched_count,
            )

    def _auto_match_grab_orders(self):
        """Auto-match collected Grab invoices with existing sale orders."""
        unmatched = self.search([
            ("provider", "=", "grab"),
            ("sale_order_id", "=", False),
            ("external_order_id", "!=", False),
            ("state", "=", "draft"),
        ])
        matched_count = 0
        for inv in unmatched:
            try:
                so = self.env["sale.order"].search([
                    ("x_grab_order_id", "=", inv.external_order_id),
                ], limit=1)
                if so:
                    inv.write({
                        "sale_order_id": so.id,
                        "partner_id": so.partner_id.id,
                        "state": "matched",
                    })
                    matched_count += 1
                    self.env["ntp.collector.log"].log_operation(
                        config=inv.config_id,
                        provider="grab",
                        operation="match",
                        invoice=inv,
                        success=True,
                    )
            except Exception as e:
                _logger.warning(
                    "Auto-match error for invoice %s: %s", inv.name, e,
                )

        if matched_count:
            _logger.info(
                "Auto-matched %d Grab invoices with sale orders", matched_count,
            )

    def action_match_sale_order(self):
        """Manual button: try to match with sale order via external_order_id."""
        for rec in self:
            if not rec.external_order_id:
                rec.message_post(body="No external order ID to match.")
                continue

            try:
                if rec.provider == "shopee":
                    domain = [("x_shopee_order_id", "=", rec.external_order_id)]
                elif rec.provider == "grab":
                    domain = [("x_grab_order_id", "=", rec.external_order_id)]
                else:
                    domain = [
                        "|",
                        ("x_shopee_order_id", "=", rec.external_order_id),
                        ("x_grab_order_id", "=", rec.external_order_id),
                    ]

                so = self.env["sale.order"].search(domain, limit=1)
                if so:
                    rec.write({
                        "sale_order_id": so.id,
                        "partner_id": so.partner_id.id,
                        "state": "matched",
                    })
                    rec.message_post(
                        body="Matched with Sale Order: %s" % so.name,
                    )
                    self.env["ntp.collector.log"].log_operation(
                        config=rec.config_id,
                        provider=rec.provider,
                        operation="match",
                        invoice=rec,
                        success=True,
                    )
                else:
                    rec.message_post(
                        body="No matching Sale Order found for ID: %s"
                        % rec.external_order_id,
                    )
                    self.env["ntp.collector.log"].log_operation(
                        config=rec.config_id,
                        provider=rec.provider,
                        operation="match",
                        invoice=rec,
                        success=False,
                        error_message="No matching SO found",
                    )
            except Exception as e:
                _logger.error(
                    "Manual match error for %s: %s", rec.name, e, exc_info=True,
                )
                rec.message_post(
                    body="Match error: %s" % str(e),
                )

    # ====================================================================
    # Bizzi Integration (Reuses ntp_cne Bizzi config)
    # ====================================================================

    def action_push_to_bizzi(self):
        """Manual button: push selected records to Bizzi."""
        for rec in self:
            try:
                rec._push_to_bizzi()
            except Exception as e:
                rec.write({
                    "bizzi_status": "error",
                    "error_message": str(e)[:1000],
                    "last_error_date": fields.Datetime.now(),
                })
                _logger.error(
                    "Bizzi push error for %s: %s", rec.name, e, exc_info=True,
                )
                self.env["ntp.collector.log"].log_operation(
                    config=rec.config_id,
                    provider=rec.provider,
                    operation="push_bizzi",
                    invoice=rec,
                    success=False,
                    error_message=str(e),
                )

    def _push_to_bizzi(self):
        """Upload a single invoice record to Bizzi for VAT verification.

        Reuses the Bizzi API URL and API Key stored in ir.config_parameter
        by the ntp_cne module (keys: tax_invoice.tax_invoice_bizzi_api_url,
        tax_invoice.tax_invoice_bizzi_api_key).
        """
        self.ensure_one()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
        api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")

        if not api_url or not api_key:
            raise UserError(
                "Bizzi API is not configured. "
                "Go to Settings > Accounting > Tax Invoice > Bizzi Config "
                "to set up the API URL and API Key."
            )

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        }

        # Build invoice payload for Bizzi
        payload = {
            "invoice_number": self.name,
            "invoice_date": self.transaction_date.isoformat() if self.transaction_date else "",
            "total_amount": self.total_amount,
            "currency": self.currency_id.name if self.currency_id else "VND",
            "source": self.provider,
            "external_order_id": self.external_order_id or "",
            "partner_name": self.partner_id.name if self.partner_id else "",
            "partner_vat": self.partner_id.vat if self.partner_id else "",
        }

        # Include attachment data if available
        if self.attachment_ids:
            attachment = self.attachment_ids[0]
            payload["attachment_name"] = attachment.name
            payload["attachment_data"] = attachment.datas.decode("utf-8") if attachment.datas else ""

        url = urljoin(api_url, "v1/invoices")
        start_time = time.time()

        try:
            response = self._make_request(
                "post", url, config=self.config_id,
                json=payload, headers=headers,
            )
            duration = time.time() - start_time

            if response.status_code in (200, 201):
                result = response.json()
                bizzi_id = result.get("data", {}).get(
                    "invoice_id", result.get("id", "")
                )
                self.write({
                    "bizzi_invoice_id": str(bizzi_id) if bizzi_id else "",
                    "bizzi_status": "uploaded",
                    "state": "pushed",
                    "error_message": False,
                })
                self.message_post(
                    body="Invoice successfully uploaded to Bizzi. "
                    "Bizzi ID: %s" % bizzi_id,
                )
                self.env["ntp.collector.log"].log_operation(
                    config=self.config_id,
                    provider=self.provider,
                    operation="push_bizzi",
                    invoice=self,
                    success=True,
                    request_url=url,
                    response_code=response.status_code,
                    duration_seconds=duration,
                )
            else:
                error_text = response.text[:500]
                self.write({
                    "bizzi_status": "error",
                    "error_message": "HTTP %d: %s" % (
                        response.status_code, error_text,
                    ),
                    "last_error_date": fields.Datetime.now(),
                })
                self.message_post(
                    body="Bizzi upload failed (HTTP %d): %s"
                    % (response.status_code, error_text),
                )
                self.env["ntp.collector.log"].log_operation(
                    config=self.config_id,
                    provider=self.provider,
                    operation="push_bizzi",
                    invoice=self,
                    success=False,
                    request_url=url,
                    response_code=response.status_code,
                    response_summary=error_text,
                    error_message="HTTP %d" % response.status_code,
                    duration_seconds=duration,
                )
        except requests.RequestException as e:
            self.env["ntp.collector.log"].log_operation(
                config=self.config_id,
                provider=self.provider,
                operation="push_bizzi",
                invoice=self,
                success=False,
                request_url=url,
                error_message=str(e),
            )
            raise UserError("Bizzi API request failed: %s" % str(e))

    # ====================================================================
    # State Actions
    # ====================================================================

    def action_set_verified(self):
        """Manually mark as verified (e.g., after Bizzi webhook callback)."""
        self.write({
            "state": "verified",
            "bizzi_status": "verified",
        })
        _logger.info(
            "Invoices marked as verified: %s",
            ", ".join(self.mapped("name")),
        )

    def action_reset_to_draft(self):
        """Reset error records back to draft for retry."""
        for rec in self:
            rec.write({
                "state": "draft",
                "bizzi_status": "pending",
                "error_message": False,
                "retry_count": rec.retry_count + 1,
            })
        _logger.info(
            "Invoices reset to draft: %s",
            ", ".join(self.mapped("name")),
        )

    def action_retry_failed(self):
        """Retry all failed invoices."""
        failed = self.filtered(lambda r: r.state == "error" or r.bizzi_status == "error")
        if not failed:
            raise UserError("No failed invoices to retry.")

        _logger.info("Retrying %d failed invoices", len(failed))
        for inv in failed:
            try:
                inv.write({
                    "state": "draft",
                    "bizzi_status": "pending",
                    "error_message": False,
                    "retry_count": inv.retry_count + 1,
                })
                self.env["ntp.collector.log"].log_operation(
                    config=inv.config_id,
                    provider=inv.provider,
                    operation="retry",
                    invoice=inv,
                    success=True,
                )
            except Exception as e:
                _logger.error(
                    "Error retrying invoice %s: %s", inv.name, e,
                )
