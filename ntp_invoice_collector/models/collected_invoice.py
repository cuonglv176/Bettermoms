# -*- coding: utf-8 -*-

import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta

import requests
from urllib.parse import urljoin

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
    # Cron Entry Points
    # ====================================================================

    @api.model
    def cron_fetch_invoices(self):
        """Scheduled action: fetch invoices from all active collector configs."""
        configs = self.env["ntp.collector.config"].search(
            [("is_active", "=", True)]
        )
        for config in configs:
            try:
                if config.provider == "shopee":
                    self._fetch_shopee_invoices(config)
                elif config.provider == "grab":
                    self._fetch_grab_invoices(config)
                config.last_sync_date = fields.Datetime.now()
                _logger.info(
                    "Invoice fetch completed for config: %s", config.name
                )
            except Exception as e:
                _logger.error(
                    "Invoice fetch error for %s: %s", config.name, e,
                    exc_info=True,
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
        for inv in pending:
            try:
                inv._push_to_bizzi()
            except Exception as e:
                inv.write({
                    "bizzi_status": "error",
                    "error_message": str(e),
                })
                _logger.error(
                    "Bizzi push error for %s: %s", inv.name, e,
                    exc_info=True,
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

        partner_id = int(config.api_key or 0)
        shop_id = int(config.shop_id or 0)

        # Calculate time range
        now = int(time.time())
        if config.last_sync_date:
            time_from = int(config.last_sync_date.timestamp())
        else:
            # Default: last 30 days
            time_from = now - (30 * 24 * 3600)

        path = "/api/v2/order/get_order_list"
        timestamp = now

        # HMAC signing for Shopee Open Platform
        sign_base = "%d%s%d%s%d" % (
            partner_id, path, timestamp,
            config.access_token or "", shop_id,
        )
        sign = hmac.new(
            (config.api_secret or "").encode("utf-8"),
            sign_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

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
        while has_more:
            try:
                url = "%s%s" % (base_url, path)
                response = requests.get(url, params=params, timeout=30)
                data = response.json()

                if data.get("error"):
                    _logger.warning(
                        "Shopee API error: %s - %s",
                        data.get("error"), data.get("message"),
                    )
                    break

                resp = data.get("response", {})
                order_list = resp.get("order_list", [])

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
                    detail = self._shopee_get_order_detail(
                        config, base_url, partner_id, shop_id, order_sn,
                    )

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
                else:
                    has_more = False

            except requests.RequestException as e:
                _logger.error("Shopee API request error: %s", e)
                break

        # Auto-match fetched invoices with existing sale orders
        self._auto_match_shopee_orders()
        return count

    def _shopee_get_order_detail(self, config, base_url, partner_id, shop_id, order_sn):
        """Fetch single order detail from Shopee for amount info."""
        path = "/api/v2/order/get_order_detail"
        timestamp = int(time.time())
        sign_base = "%d%s%d%s%d" % (
            partner_id, path, timestamp,
            config.access_token or "", shop_id,
        )
        sign = hmac.new(
            (config.api_secret or "").encode("utf-8"),
            sign_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

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
            response = requests.get(url, params=params, timeout=15)
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
        """Fetch completed transactions from Grab API.

        Returns the count of new invoices created.
        """
        count = 0
        base_url = (config.api_url or "").rstrip("/")
        if not base_url:
            raise UserError("Grab API URL is not configured.")

        headers = {
            "Authorization": "Bearer %s" % (config.access_token or config.api_key or ""),
            "Content-Type": "application/json",
        }

        # Calculate time range
        if config.last_sync_date:
            date_from = config.last_sync_date.strftime("%Y-%m-%d")
        else:
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        # Grab Transaction History endpoint
        url = "%s/v1/transactions" % base_url
        params = {
            "startDate": date_from,
            "endDate": date_to,
            "status": "COMPLETED",
            "page": 1,
            "pageSize": 50,
        }

        has_more = True
        while has_more:
            try:
                response = requests.get(
                    url, params=params, headers=headers, timeout=30,
                )
                if response.status_code != 200:
                    _logger.warning(
                        "Grab API error (HTTP %d): %s",
                        response.status_code, response.text[:500],
                    )
                    break

                data = response.json()
                transactions = data.get("data", data.get("transactions", []))

                for txn in transactions:
                    txn_id = txn.get("transactionID", txn.get("id", ""))
                    if not txn_id:
                        continue

                    # Skip if already collected
                    existing = self.search([
                        ("provider", "=", "grab"),
                        ("external_order_id", "=", str(txn_id)),
                    ], limit=1)
                    if existing:
                        continue

                    txn_date = txn.get("completedAt", txn.get("date", ""))
                    try:
                        parsed_date = fields.Date.from_string(txn_date[:10])
                    except Exception:
                        parsed_date = fields.Date.today()

                    vals = {
                        "name": "GRAB-%s" % txn_id,
                        "provider": "grab",
                        "config_id": config.id,
                        "external_order_id": str(txn_id),
                        "transaction_date": parsed_date,
                        "total_amount": float(
                            txn.get("amount", txn.get("totalAmount", 0))
                        ),
                        "state": "draft",
                        "bizzi_status": "pending",
                    }
                    try:
                        self.sudo().create(vals)
                        count += 1
                    except Exception as e:
                        _logger.warning(
                            "Failed to create invoice for Grab txn %s: %s",
                            txn_id, e,
                        )

                # Pagination
                pagination = data.get("pagination", {})
                total_pages = pagination.get("totalPages", 1)
                current_page = params["page"]
                if current_page < total_pages:
                    params["page"] = current_page + 1
                else:
                    has_more = False

            except requests.RequestException as e:
                _logger.error("Grab API request error: %s", e)
                break

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
        for inv in unmatched:
            so = self.env["sale.order"].search([
                ("x_shopee_order_id", "=", inv.external_order_id),
            ], limit=1)
            if so:
                inv.write({
                    "sale_order_id": so.id,
                    "partner_id": so.partner_id.id,
                    "state": "matched",
                })

    def action_match_sale_order(self):
        """Manual button: try to match with sale order via external_order_id."""
        for rec in self:
            if rec.external_order_id:
                domain = [("x_shopee_order_id", "=", rec.external_order_id)]
                so = self.env["sale.order"].search(domain, limit=1)
                if so:
                    rec.write({
                        "sale_order_id": so.id,
                        "partner_id": so.partner_id.id,
                        "state": "matched",
                    })
                else:
                    rec.message_post(
                        body="No matching Sale Order found for ID: %s"
                        % rec.external_order_id,
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
                    "error_message": str(e),
                })
                _logger.error(
                    "Bizzi push error for %s: %s", rec.name, e, exc_info=True,
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
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=30,
            )
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
            else:
                error_text = response.text[:500]
                self.write({
                    "bizzi_status": "error",
                    "error_message": "HTTP %d: %s" % (
                        response.status_code, error_text,
                    ),
                })
                self.message_post(
                    body="Bizzi upload failed (HTTP %d): %s"
                    % (response.status_code, error_text),
                )
        except requests.RequestException as e:
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

    def action_reset_to_draft(self):
        """Reset error records back to draft for retry."""
        self.write({
            "state": "draft",
            "bizzi_status": "pending",
            "error_message": False,
        })
