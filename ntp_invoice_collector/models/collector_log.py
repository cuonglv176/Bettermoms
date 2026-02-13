# -*- coding: utf-8 -*-
"""
Invoice Collector Log History
==============================
Tracks all invoice collection operations, API calls, and errors
for auditing and troubleshooting purposes.
"""

import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class CollectorLog(models.Model):
    _name = "ntp.collector.log"
    _description = "Invoice Collector Log"
    _order = "create_date desc"

    config_id = fields.Many2one(
        "ntp.collector.config", "Configuration",
        ondelete="set null",
        index=True,
    )
    config_name = fields.Char(
        "Config Name",
        help="Stored separately in case config is deleted.",
    )
    provider = fields.Selection(
        [
            ("shopee", "Shopee"),
            ("grab", "Grab"),
        ],
        string="Provider",
        index=True,
    )
    operation = fields.Selection(
        [
            ("fetch", "Fetch Invoices"),
            ("match", "Match Sale Order"),
            ("push_bizzi", "Push to Bizzi"),
            ("test_connection", "Test Connection"),
            ("retry", "Retry"),
        ],
        string="Operation",
        required=True,
        index=True,
    )
    invoice_id = fields.Many2one(
        "ntp.collected.invoice", "Related Invoice",
        ondelete="set null",
    )
    success = fields.Boolean("Success", default=True)
    records_processed = fields.Integer(
        "Records Processed",
        help="Number of records fetched/matched/pushed in this operation.",
    )
    error_message = fields.Text("Error Details")
    request_url = fields.Char("Request URL")
    response_code = fields.Integer("HTTP Response Code")
    response_summary = fields.Text(
        "Response Summary",
        help="Truncated response body for debugging.",
    )
    duration_seconds = fields.Float(
        "Duration (s)",
        digits=(10, 2),
        help="Time taken for the operation in seconds.",
    )
    user_id = fields.Many2one(
        "res.users", "User",
        default=lambda self: self.env.uid,
    )

    @api.model
    def log_operation(self, config=None, provider="", operation="fetch",
                      invoice=None, success=True, records_processed=0,
                      error_message="", request_url="", response_code=0,
                      response_summary="", duration_seconds=0.0):
        """Create a log entry for a collector operation.

        This method is designed to never raise exceptions - it logs
        errors internally and returns False on failure.
        """
        try:
            vals = {
                "config_id": config.id if config else False,
                "config_name": config.name if config else "",
                "provider": provider or (config.provider if config else ""),
                "operation": operation,
                "invoice_id": invoice.id if invoice else False,
                "success": success,
                "records_processed": records_processed,
                "error_message": (error_message or "")[:2000] if error_message else False,
                "request_url": (request_url or "")[:500],
                "response_code": response_code,
                "response_summary": (response_summary or "")[:1000] if response_summary else False,
                "duration_seconds": duration_seconds,
            }
            record = self.sudo().create(vals)
            _logger.debug(
                "Collector log created: config=%s, op=%s, success=%s, records=%d",
                config.name if config else "N/A", operation, success, records_processed,
            )
            return record
        except Exception as e:
            _logger.error(
                "Failed to create collector log: %s", e, exc_info=True,
            )
            return False
