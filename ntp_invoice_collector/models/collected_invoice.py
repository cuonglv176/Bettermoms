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
            ("spv", "SPV Tracuuhoadon"),
            ("shinhan", "Shinhan Bank eInvoice"),
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
                    # Skip if no way to authenticate automatically
                    has_session = bool(config.grab_session_cookie)
                    has_auto_captcha = (
                        getattr(config, "grab_use_auto_captcha", False)
                        and bool(getattr(config, "grab_openai_api_key", ""))
                    )
                    if not has_session and not has_auto_captcha:
                        _logger.warning(
                            "Cron skipping Grab config '%s': no active session "
                            "and auto-CAPTCHA not configured. Login manually once "
                            "or set an OpenAI API key to enable auto-CAPTCHA.",
                            config.name,
                        )
                        self.env["ntp.collector.log"].log_operation(
                            config=config,
                            operation="fetch",
                            success=False,
                            error_message=(
                                "Cron skipped: no session cookie and auto-CAPTCHA "
                                "not configured. Login manually once, or enable "
                                "auto-CAPTCHA with an OpenAI API key."
                            ),
                        )
                        continue
                    count = self._fetch_grab_portal_invoices(config)
                elif config.provider == "spv":
                    has_session = bool(config.spv_session_cookie)
                    has_auto_captcha = (
                        getattr(config, "spv_use_auto_captcha", False)
                        and bool(getattr(config, "spv_openai_api_key", ""))
                    )
                    if not has_session and not has_auto_captcha:
                        _logger.warning(
                            "Cron skipping SPV config '%s': no active session "
                            "and auto-CAPTCHA not configured.",
                            config.name,
                        )
                        self.env["ntp.collector.log"].log_operation(
                            config=config,
                            operation="fetch",
                            success=False,
                            error_message=(
                                "Cron skipped: no session cookie and auto-CAPTCHA "
                                "not configured. Enable auto-CAPTCHA with an OpenAI API key."
                            ),
                        )
                        continue
                    count = self._fetch_spv_portal_invoices(config)
                elif config.provider == "shinhan":
                    has_jwt = bool(config.shinhan_jwt_token)
                    has_auto_captcha = (
                        getattr(config, "shinhan_use_auto_captcha", False)
                        and bool(getattr(config, "shinhan_openai_api_key", ""))
                    )
                    if not has_jwt and not has_auto_captcha:
                        _logger.warning(
                            "Cron skipping Shinhan config '%s': no active JWT token "
                            "and auto-CAPTCHA not configured.",
                            config.name,
                        )
                        self.env["ntp.collector.log"].log_operation(
                            config=config,
                            operation="fetch",
                            success=False,
                            error_message=(
                                "Cron skipped: no JWT token and auto-CAPTCHA "
                                "not configured. Enable auto-CAPTCHA with an OpenAI API key."
                            ),
                        )
                        continue
                    count = self._fetch_shinhan_portal_invoices(config)
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

                    # Build notes with order detail info
                    notes_parts = []
                    if detail.get("items_text"):
                        notes_parts.append("Items: %s" % detail["items_text"])
                    if detail.get("buyer_username"):
                        notes_parts.append("Buyer: %s" % detail["buyer_username"])
                    if detail.get("shipping_carrier"):
                        notes_parts.append("Shipping: %s" % detail["shipping_carrier"])
                    if detail.get("tracking_number"):
                        notes_parts.append("Tracking: %s" % detail["tracking_number"])
                    if detail.get("payment_method"):
                        notes_parts.append("Payment: %s" % detail["payment_method"])
                    if detail.get("notes"):
                        notes_parts.append("Note: %s" % detail["notes"])

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
                        "notes": " | ".join(notes_parts) if notes_parts else "",
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
        """Fetch single order detail from Shopee for amount and item info.

        Returns dict with keys:
            total_amount, items_text, shipping_carrier, payment_method,
            buyer_username, tracking_number, notes
        """
        path = "/api/v2/order/get_order_detail"
        sign, timestamp, _, _ = self._shopee_sign(config, path)

        # Request all useful optional fields
        optional_fields = ",".join([
            "buyer_user_id", "buyer_username", "estimated_shipping_fee",
            "recipient_address", "actual_shipping_fee", "goods_to_declare",
            "note", "note_update_time", "item_list", "pay_time",
            "dropshipper", "dropshipper_phone", "split_up",
            "buyer_cancel_reason", "cancel_by", "cancel_reason",
            "actual_shipping_fee_confirmed", "buyer_cpf_id",
            "fulfillment_flag", "pickup_done_time", "package_list",
            "shipping_carrier", "payment_method", "total_amount",
            "invoice_data", "checkout_shipping_carrier",
            "reverse_shipping_fee", "order_chargeable_weight_gram",
            "edt", "prescription_images", "prescription_check_status",
        ])

        params = {
            "partner_id": partner_id,
            "timestamp": timestamp,
            "access_token": config.access_token or "",
            "shop_id": shop_id,
            "sign": sign,
            "order_sn_list": order_sn,
            "response_optional_fields": optional_fields,
        }
        result = {
            "total_amount": 0.0,
            "items_text": "",
            "shipping_carrier": "",
            "payment_method": "",
            "buyer_username": "",
            "tracking_number": "",
            "notes": "",
        }

        try:
            url = "%s%s" % (base_url, path)
            response = self._make_request("get", url, config=config, params=params)
            data = response.json()
            resp = data.get("response", {})
            orders = resp.get("order_list", [])
            if not orders:
                return result

            order = orders[0]

            # Amount
            order_income = order.get("order_income", {})
            if order_income:
                result["total_amount"] = float(
                    order_income.get("escrow_amount", 0)
                    or order_income.get("buyer_total_amount", 0)
                    or order.get("total_amount", 0)
                )
            else:
                result["total_amount"] = float(order.get("total_amount", 0))

            # Items
            item_list = order.get("item_list", [])
            if item_list:
                items_parts = []
                for item in item_list:
                    item_name = item.get("item_name", "")
                    item_qty = item.get("model_quantity_purchased", 0) or item.get("quantity", 0)
                    item_price = float(item.get("model_discounted_price", 0) or item.get("model_original_price", 0))
                    item_sku = item.get("item_sku", "")
                    items_parts.append(
                        "%s x%d @ %.0f%s" % (
                            item_name[:80], item_qty, item_price,
                            " [%s]" % item_sku if item_sku else "",
                        )
                    )
                result["items_text"] = "; ".join(items_parts)

            # Shipping
            result["shipping_carrier"] = order.get("shipping_carrier", "")
            package_list = order.get("package_list", [])
            if package_list:
                tracking_numbers = [
                    pkg.get("logistics_status", "") or pkg.get("package_number", "")
                    for pkg in package_list
                ]
                result["tracking_number"] = ", ".join(filter(None, tracking_numbers))

            # Payment & buyer
            result["payment_method"] = order.get("payment_method", "")
            result["buyer_username"] = order.get("buyer_username", "")
            result["notes"] = order.get("note", "")

        except Exception as e:
            _logger.warning("Could not fetch Shopee order detail for %s: %s", order_sn, e)

        return result

    def _fetch_grab_invoices(self, config):
        """
        Legacy method: kept for backward compatibility.
        Delegates to the new portal-based fetcher.
        """
        return self._fetch_grab_portal_invoices(config)

    def _fetch_grab_portal_invoices_with_session(self, config, session):
        """
        Fetch invoices from Grab portal using an already-authenticated session.

        This is called from action_grab_auto_fetch() after auto-login.

        Args:
            config: ntp.collector.config record.
            session: GrabEInvoiceSession instance (already authenticated).

        Returns:
            int: Number of new invoice records created.
        """
        return self._do_grab_fetch(config, session)

    def _fetch_grab_portal_invoices(self, config, captcha_answer=None):
        """
        Fetch invoices from the Grab e-invoice portal (vn.einvoice.grab.com).

        This method handles the full session-based authentication flow:
          1. Try auto-login with OpenAI CAPTCHA solving (if enabled)
          2. Or use a provided captcha_answer for manual flow
          3. Or restore session from stored cookie
          4. Paginate through the invoice list
          5. Create ntp.collected.invoice records for new invoices
          6. Optionally download PDF/XML attachments

        Args:
            config: ntp.collector.config record.
            captcha_answer (str): CAPTCHA text answer. If None, tries auto-login
                                  or stored session cookie.

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
            # Manual CAPTCHA flow: use stored CSRF token and cookies
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
                session.prepare_login()
                session.get_captcha_image()

            _logger.info(
                "Attempting Grab portal login for config '%s' (manual CAPTCHA)...",
                config.name,
            )
            login_ok = session.login(captcha_answer)

            if not login_ok:
                error_detail = session.last_error or "Unknown error"
                config.write({"grab_login_status": "error"})

                if session.is_account_locked:
                    raise UserError(
                        "\u26a0\ufe0f Grab account '%s' is LOCKED!\n\n"
                        "Contact Grab support to unlock.\n\n"
                        "Detail: %s" % (config.api_key, error_detail)
                    )

                raise UserError(
                    "Grab portal login failed for '%s'.\n\n"
                    "Please check your credentials and CAPTCHA answer.\n\n"
                    "Detail: %s" % (config.name, error_detail)
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

            # Verify session is still valid
            if not session.check_session_valid():
                _logger.info(
                    "Stored session expired for '%s', trying auto-login...",
                    config.name,
                )
                # Try auto-login
                use_auto = getattr(config, 'grab_use_auto_captcha', True)
                if use_auto:
                    openai_key = getattr(config, 'grab_openai_api_key', None) or None
                    login_ok = session.auto_login(openai_api_key=openai_key)
                    if login_ok:
                        config.write({"grab_login_status": "logged_in"})
                    else:
                        config.write({"grab_login_status": "session_expired"})
                        _logger.warning(
                            "Auto-login failed for '%s'. Manual login required.",
                            config.name,
                        )
                        return 0
                else:
                    config.write({"grab_login_status": "session_expired"})
                    return 0

        else:
            # No session — try auto-login with CAPTCHA solving
            use_auto = getattr(config, 'grab_use_auto_captcha', True)
            if use_auto:
                _logger.info(
                    "No stored session for '%s', trying auto-login with CAPTCHA solving...",
                    config.name,
                )
                openai_key = getattr(config, 'grab_openai_api_key', None) or None
                login_ok = session.auto_login(openai_api_key=openai_key)
                if login_ok:
                    config.write({"grab_login_status": "logged_in"})
                    # Store session cookie for future cron runs
                    aspx_cookie = session.get_aspx_cookie()
                    if aspx_cookie:
                        config.write({"grab_session_cookie": aspx_cookie})
                else:
                    error_detail = session.last_error or "Unknown error"
                    is_locked = session.is_account_locked
                    config.write({"grab_login_status": "error"})
                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        operation="fetch",
                        success=False,
                        error_message=(
                            "Grab auto-login failed. %s. "
                            "Detail: %s" % (
                                "Account LOCKED" if is_locked else "Manual login required",
                                error_detail,
                            )
                        ),
                    )
                    return 0
            else:
                _logger.warning(
                    "Grab config '%s' has no active session and auto-CAPTCHA is disabled.",
                    config.name,
                )
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message="No active session. Enable auto-CAPTCHA or login manually.",
                )
                return 0

        return self._do_grab_fetch(config, session)

    def _do_grab_fetch(self, config, session):
        """
        Core Grab invoice fetch logic (shared by manual and auto flows).

        Args:
            config: ntp.collector.config record.
            session: GrabEInvoiceSession instance (authenticated).

        Returns:
            int: Number of new invoice records created.
        """
        count = 0

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
                inv_number = inv_data.get("invoice_number", "")

                # Prefer invoice_number as external_id — more stable and meaningful
                # than HTML row IDs (which may change between sessions).
                external_id = str(inv_number or inv_id)
                if not external_id:
                    continue

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
                        "Series: %s | Buyer: %s | Tax: %s | Seller: %s | Status: %s"
                        % (
                            inv_data.get("series", ""),
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
                file_list = zf.namelist()
                _logger.info(
                    "Grab attachment ZIP contains %d file(s): %s",
                    len(file_list),
                    ", ".join(file_list[:20]) + ("..." if len(file_list) > 20 else ""),
                )

                for filename in file_list:
                    file_data = zf.read(filename)
                    if not file_data:
                        _logger.warning("Empty file in ZIP: '%s', skipping.", filename)
                        continue

                    # Try to match filename to an invoice external ID
                    matched_odoo_id = None
                    for ext_id in external_ids:
                        if ext_id in filename:
                            matched_odoo_id = odoo_id_map.get(ext_id)
                            break

                    if not matched_odoo_id:
                        # Cannot determine which invoice this file belongs to — skip.
                        # Attaching to a random record would cause incorrect data.
                        _logger.warning(
                            "Could not match ZIP file '%s' to any invoice "
                            "(tried %d IDs: %s). Skipping.",
                            filename,
                            len(external_ids),
                            ", ".join(external_ids[:5]) + ("..." if len(external_ids) > 5 else ""),
                        )
                        continue

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
    # SPV Portal Fetch Methods
    # ====================================================================

    def _fetch_spv_portal_invoices_with_session(self, config, session):
        """
        Fetch invoices from SPV portal using an already-authenticated session.

        Args:
            config: ntp.collector.config record.
            session: SpvEInvoiceSession instance (already authenticated).

        Returns:
            int: Number of new invoice records created.
        """
        return self._do_spv_fetch(config, session)

    def _fetch_spv_portal_invoices(self, config, captcha_answer=None):
        """
        Fetch invoices from the SPV Tracuuhoadon portal (spv.tracuuhoadon.online).

        Handles the full session-based authentication flow:
          1. Try auto-login with OpenAI CAPTCHA solving (if enabled)
          2. Or use a provided captcha_answer for manual flow
          3. Or restore session from stored cookie
          4. Paginate through the invoice list
          5. Create ntp.collected.invoice records for new invoices

        Args:
            config: ntp.collector.config record.
            captcha_answer (str): CAPTCHA text answer for manual flow.

        Returns:
            int: Number of new invoice records created.
        """
        from .spv_session import SpvEInvoiceSession

        base_url = (config.api_url or "").rstrip("/") or "https://spv.tracuuhoadon.online"

        if not config.api_key:
            raise UserError(
                "SPV Username (maKh) is not configured for '%s'." % config.name
            )
        if not config.api_secret:
            raise UserError(
                "SPV Password is not configured for '%s'." % config.name
            )

        session = SpvEInvoiceSession(
            username=config.api_key,
            password=config.api_secret,
            base_url=base_url,
        )

        if captcha_answer:
            # Manual CAPTCHA flow: restore stored session state
            csrf_key = "ntp_invoice_collector.spv_csrf_%d" % config.id
            nonce_key = "ntp_invoice_collector.spv_nonce_%d" % config.id
            cookie_key = "ntp_invoice_collector.spv_cookies_%d" % config.id
            get_param = self.env["ir.config_parameter"].sudo().get_param

            session._csrf_token = get_param(csrf_key, default="")
            session._nonce = get_param(nonce_key, default="")
            cookies_json = get_param(cookie_key, default="{}")
            session.restore_session(cookies_json)

            if not session._csrf_token:
                session.prepare_login()
                session.get_captcha_image_b64()

            _logger.info(
                "Attempting SPV portal login for config '%s' (manual CAPTCHA)...",
                config.name,
            )
            login_ok = session.login(captcha_answer)

            if not login_ok:
                error_detail = session.last_error or "Unknown error"
                config.write({"spv_login_status": "error"})

                if session.is_account_locked:
                    raise UserError(
                        "\u26a0\ufe0f SPV account '%s' is LOCKED!\n\n"
                        "Contact SPV support to unlock.\n\n"
                        "Detail: %s" % (config.api_key, error_detail)
                    )

                raise UserError(
                    "SPV portal login failed for '%s'.\n\n"
                    "Please check your credentials and CAPTCHA answer.\n\n"
                    "Detail: %s" % (config.name, error_detail)
                )

            config.write({"spv_login_status": "logged_in"})

        elif config.spv_session_cookie:
            # Restore session from stored cookie
            _logger.info(
                "Restoring SPV session from stored cookie for config '%s'",
                config.name,
            )
            session.restore_session(json.dumps({".ASPXAUTH": config.spv_session_cookie}))

            if not session.check_session_valid():
                _logger.info(
                    "Stored SPV session expired for '%s', trying auto-login...",
                    config.name,
                )
                use_auto = getattr(config, "spv_use_auto_captcha", True)
                if use_auto:
                    openai_key = getattr(config, "spv_openai_api_key", None) or None
                    login_ok = session.auto_login(openai_api_key=openai_key)
                    if login_ok:
                        config.write({"spv_login_status": "logged_in"})
                    else:
                        config.write({"spv_login_status": "session_expired"})
                        _logger.warning(
                            "SPV auto-login failed for '%s'. Manual login required.",
                            config.name,
                        )
                        return 0
                else:
                    config.write({"spv_login_status": "session_expired"})
                    return 0

        else:
            # No session — try auto-login
            use_auto = getattr(config, "spv_use_auto_captcha", True)
            if use_auto:
                _logger.info(
                    "No stored SPV session for '%s', trying auto-login...",
                    config.name,
                )
                openai_key = getattr(config, "spv_openai_api_key", None) or None
                login_ok = session.auto_login(openai_api_key=openai_key)
                if login_ok:
                    config.write({"spv_login_status": "logged_in"})
                    cookie_val = session.get_session_cookie()
                    if cookie_val:
                        config.write({"spv_session_cookie": cookie_val})
                else:
                    error_detail = session.last_error or "Unknown error"
                    config.write({"spv_login_status": "error"})
                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        operation="fetch",
                        success=False,
                        error_message="SPV auto-login failed. Detail: %s" % error_detail,
                    )
                    return 0
            else:
                _logger.warning(
                    "SPV config '%s' has no active session and auto-CAPTCHA is disabled.",
                    config.name,
                )
                return 0

        return self._do_spv_fetch(config, session)

    def _do_spv_fetch(self, config, session):
        """
        Core SPV invoice fetch logic.

        Args:
            config: ntp.collector.config record.
            session: SpvEInvoiceSession instance (authenticated).

        Returns:
            int: Number of new invoice records created.
        """
        count = 0

        # Calculate date range
        if config.spv_date_from:
            date_from_dt = config.spv_date_from
        elif config.last_sync_date:
            date_from_dt = config.last_sync_date.date()
        else:
            date_from_dt = (datetime.now() - timedelta(days=30)).date()

        date_to_dt = datetime.now().date()
        date_from_str = date_from_dt.strftime("%d/%m/%Y")
        date_to_str = date_to_dt.strftime("%d/%m/%Y")

        _logger.info(
            "Fetching SPV invoices for config '%s': %s to %s",
            config.name, date_from_str, date_to_str,
        )

        page = 1
        page_size = 50
        has_more = True

        while has_more:
            try:
                result = session.fetch_invoices(
                    date_from=date_from_str,
                    date_to=date_to_str,
                    page=page,
                    page_size=page_size,
                )
            except ValueError as e:
                _logger.warning(
                    "SPV session expired for config '%s': %s", config.name, e
                )
                config.write({"spv_login_status": "session_expired"})
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message="Session expired: %s" % str(e),
                )
                break
            except Exception as e:
                _logger.error(
                    "Error fetching SPV invoices (page %d): %s", page, e
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
                "SPV portal page %d: %d invoices returned (has_more=%s)",
                page, len(invoices), has_more,
            )

            if not invoices:
                break

            for inv_data in invoices:
                inv_number = str(inv_data.get("invoice_number", "") or inv_data.get("id", ""))
                if not inv_number:
                    continue

                # Skip if already collected
                existing = self.search([
                    ("provider", "=", "spv"),
                    ("external_order_id", "=", inv_number),
                ], limit=1)
                if existing:
                    continue

                raw_date = inv_data.get("invoice_date", "")
                parsed_date = self._parse_grab_date(raw_date)  # Reuse date parser

                vals = {
                    "name": "SPV-%s" % inv_number,
                    "provider": "spv",
                    "config_id": config.id,
                    "external_order_id": inv_number,
                    "transaction_date": parsed_date,
                    "total_amount": float(inv_data.get("total_amount", 0) or 0),
                    "state": "draft",
                    "bizzi_status": "pending",
                    "notes": (
                        "Series: %s | Seller: %s | Seller Tax: %s | "
                        "Buyer: %s | Buyer Tax: %s | Status: %s"
                        % (
                            inv_data.get("series", ""),
                            inv_data.get("seller_name", ""),
                            inv_data.get("seller_tax_code", ""),
                            inv_data.get("buyer_name", ""),
                            inv_data.get("buyer_tax_code", ""),
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
                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        provider="spv",
                        operation="fetch",
                        invoice=new_rec,
                        success=True,
                    )
                    _logger.debug(
                        "Created SPV invoice record: %s", vals["name"]
                    )
                except Exception as e:
                    _logger.warning(
                        "Failed to create SPV invoice record for %s: %s",
                        inv_number, e,
                    )

            page += 1
            if page > 100:
                _logger.warning("SPV fetch: reached page limit (100), stopping.")
                break

        # Store session cookie for future cron runs
        cookie_val = session.get_session_cookie()
        if cookie_val:
            config.write({"spv_session_cookie": cookie_val})

        _logger.info(
            "SPV portal fetch completed for config '%s': %d new invoices",
            config.name, count,
        )
        return count

    # ====================================================================
    # Shinhan Portal Fetch Methods
    # ====================================================================

    def _fetch_shinhan_portal_invoices_with_session(self, config, session):
        """
        Fetch invoices from Shinhan portal using an already-authenticated session.

        Args:
            config: ntp.collector.config record.
            session: ShinhanEInvoiceSession instance (already authenticated).

        Returns:
            int: Number of new invoice records created.
        """
        return self._do_shinhan_fetch(config, session)

    def _fetch_shinhan_portal_invoices(self, config, captcha_answer=None):
        """
        Fetch invoices from the Shinhan Bank e-invoice portal (einvoice.shinhan.com.vn).

        Handles the full JWT-based authentication flow:
          1. Try auto-login with OpenAI CAPTCHA solving (if enabled)
          2. Or use a provided captcha_answer for manual flow
          3. Or restore JWT token from stored value
          4. Paginate through the invoice list via REST API
          5. Create ntp.collected.invoice records for new invoices

        Args:
            config: ntp.collector.config record.
            captcha_answer (str): CAPTCHA text answer for manual flow.

        Returns:
            int: Number of new invoice records created.
        """
        from .shinhan_session import ShinhanEInvoiceSession

        base_url = (config.api_url or "").rstrip("/") or "https://einvoice.shinhan.com.vn"

        if not config.api_key:
            raise UserError(
                "Shinhan Username is not configured for '%s'." % config.name
            )
        if not config.api_secret:
            raise UserError(
                "Shinhan Password is not configured for '%s'." % config.name
            )

        session = ShinhanEInvoiceSession(
            username=config.api_key,
            password=config.api_secret,
            base_url=base_url,
        )

        if captcha_answer:
            # Manual CAPTCHA flow
            captcha_key = "ntp_invoice_collector.shinhan_captcha_text_%d" % config.id
            server_captcha = self.env["ir.config_parameter"].sudo().get_param(
                captcha_key, default=""
            )
            if server_captcha:
                session._captcha_text = server_captcha

            _logger.info(
                "Attempting Shinhan portal login for config '%s' (manual CAPTCHA)...",
                config.name,
            )
            login_ok = session.login(captcha_answer)

            if not login_ok:
                error_detail = session.last_error or "Unknown error"
                config.write({"shinhan_login_status": "error"})

                if session.is_account_locked:
                    raise UserError(
                        "\u26a0\ufe0f Shinhan account '%s' is LOCKED!\n\n"
                        "Contact Shinhan Bank support to unlock.\n\n"
                        "Detail: %s" % (config.api_key, error_detail)
                    )

                raise UserError(
                    "Shinhan portal login failed for '%s'.\n\n"
                    "Please check your credentials and CAPTCHA answer.\n\n"
                    "Detail: %s" % (config.name, error_detail)
                )

            # Store JWT token
            jwt_token = session.get_jwt_token()
            token_expiry = session.get_token_expiry()
            config.write({
                "shinhan_login_status": "logged_in",
                "shinhan_jwt_token": jwt_token or "",
                "shinhan_token_valid_until": token_expiry or (
                    fields.Datetime.now() + timedelta(minutes=30)
                ),
            })

        elif config.shinhan_jwt_token:
            # Restore JWT token
            _logger.info(
                "Restoring Shinhan JWT token for config '%s'",
                config.name,
            )
            session.restore_jwt(config.shinhan_jwt_token)

            if not session.check_session_valid():
                _logger.info(
                    "Stored Shinhan JWT expired for '%s', trying auto-login...",
                    config.name,
                )
                use_auto = getattr(config, "shinhan_use_auto_captcha", True)
                if use_auto:
                    openai_key = getattr(config, "shinhan_openai_api_key", None) or None
                    login_ok = session.auto_login(openai_api_key=openai_key)
                    if login_ok:
                        jwt_token = session.get_jwt_token()
                        token_expiry = session.get_token_expiry()
                        config.write({
                            "shinhan_login_status": "logged_in",
                            "shinhan_jwt_token": jwt_token or "",
                            "shinhan_token_valid_until": token_expiry or (
                                fields.Datetime.now() + timedelta(minutes=30)
                            ),
                        })
                    else:
                        config.write({"shinhan_login_status": "session_expired"})
                        _logger.warning(
                            "Shinhan auto-login failed for '%s'. Manual login required.",
                            config.name,
                        )
                        return 0
                else:
                    config.write({"shinhan_login_status": "session_expired"})
                    return 0

        else:
            # No JWT — try auto-login
            use_auto = getattr(config, "shinhan_use_auto_captcha", True)
            if use_auto:
                _logger.info(
                    "No stored Shinhan JWT for '%s', trying auto-login...",
                    config.name,
                )
                openai_key = getattr(config, "shinhan_openai_api_key", None) or None
                login_ok = session.auto_login(openai_api_key=openai_key)
                if login_ok:
                    jwt_token = session.get_jwt_token()
                    token_expiry = session.get_token_expiry()
                    config.write({
                        "shinhan_login_status": "logged_in",
                        "shinhan_jwt_token": jwt_token or "",
                        "shinhan_token_valid_until": token_expiry or (
                            fields.Datetime.now() + timedelta(minutes=30)
                        ),
                    })
                else:
                    error_detail = session.last_error or "Unknown error"
                    config.write({"shinhan_login_status": "error"})
                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        operation="fetch",
                        success=False,
                        error_message="Shinhan auto-login failed. Detail: %s" % error_detail,
                    )
                    return 0
            else:
                _logger.warning(
                    "Shinhan config '%s' has no active JWT and auto-CAPTCHA is disabled.",
                    config.name,
                )
                return 0

        return self._do_shinhan_fetch(config, session)

    def _do_shinhan_fetch(self, config, session):
        """
        Core Shinhan invoice fetch logic.

        Args:
            config: ntp.collector.config record.
            session: ShinhanEInvoiceSession instance (authenticated).

        Returns:
            int: Number of new invoice records created.
        """
        count = 0

        # Calculate date range
        if config.shinhan_date_from:
            date_from_dt = config.shinhan_date_from
        elif config.last_sync_date:
            date_from_dt = config.last_sync_date.date()
        else:
            date_from_dt = (datetime.now() - timedelta(days=30)).date()

        date_to_dt = datetime.now().date()
        date_from_str = date_from_dt.strftime("%Y-%m-%d")
        date_to_str = date_to_dt.strftime("%Y-%m-%d")

        _logger.info(
            "Fetching Shinhan invoices for config '%s': %s to %s",
            config.name, date_from_str, date_to_str,
        )

        page = 1
        page_size = 50
        has_more = True

        while has_more:
            try:
                result = session.fetch_invoices(
                    date_from=date_from_str,
                    date_to=date_to_str,
                    page=page,
                    page_size=page_size,
                )
            except ValueError as e:
                _logger.warning(
                    "Shinhan JWT expired for config '%s': %s", config.name, e
                )
                config.write({"shinhan_login_status": "session_expired"})
                self.env["ntp.collector.log"].log_operation(
                    config=config,
                    operation="fetch",
                    success=False,
                    error_message="JWT expired: %s" % str(e),
                )
                break
            except Exception as e:
                _logger.error(
                    "Error fetching Shinhan invoices (page %d): %s", page, e
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
                "Shinhan portal page %d: %d invoices returned (has_more=%s)",
                page, len(invoices), has_more,
            )

            if not invoices:
                break

            for inv_data in invoices:
                inv_number = str(inv_data.get("invoice_number", "") or inv_data.get("id", ""))
                if not inv_number:
                    continue

                # Skip if already collected
                existing = self.search([
                    ("provider", "=", "shinhan"),
                    ("external_order_id", "=", inv_number),
                ], limit=1)
                if existing:
                    continue

                raw_date = inv_data.get("invoice_date", "")
                parsed_date = self._parse_grab_date(raw_date)  # Reuse date parser

                vals = {
                    "name": "SHINHAN-%s" % inv_number,
                    "provider": "shinhan",
                    "config_id": config.id,
                    "external_order_id": inv_number,
                    "transaction_date": parsed_date,
                    "total_amount": float(inv_data.get("total_amount", 0) or 0),
                    "state": "draft",
                    "bizzi_status": "pending",
                    "notes": (
                        "Series: %s | Seller: %s | Seller Tax: %s | "
                        "Buyer: %s | Buyer Tax: %s | Type: %s | Status: %s"
                        % (
                            inv_data.get("series", ""),
                            inv_data.get("seller_name", ""),
                            inv_data.get("seller_tax_code", ""),
                            inv_data.get("buyer_name", ""),
                            inv_data.get("buyer_tax_code", ""),
                            inv_data.get("invoice_type", ""),
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
                    self.env["ntp.collector.log"].log_operation(
                        config=config,
                        provider="shinhan",
                        operation="fetch",
                        invoice=new_rec,
                        success=True,
                    )
                    _logger.debug(
                        "Created Shinhan invoice record: %s", vals["name"]
                    )
                except Exception as e:
                    _logger.warning(
                        "Failed to create Shinhan invoice record for %s: %s",
                        inv_number, e,
                    )

            page += 1
            if page > 100:
                _logger.warning("Shinhan fetch: reached page limit (100), stopping.")
                break

        # Update stored JWT token
        jwt_token = session.get_jwt_token()
        if jwt_token:
            config.write({"shinhan_jwt_token": jwt_token})

        _logger.info(
            "Shinhan portal fetch completed for config '%s': %d new invoices",
            config.name, count,
        )
        return count

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
