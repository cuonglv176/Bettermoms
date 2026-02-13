# -*- coding: utf-8 -*-
"""
Address Lookup Log History
===========================
Tracks all address lookup and auto-detect operations for auditing
and troubleshooting purposes.
"""

import logging

from odoo import models, fields, api

logger = logging.getLogger(__name__)


class AddressLookupLog(models.Model):
    _name = "address.lookup.log"
    _description = "Address Lookup Log"
    _order = "create_date desc"
    _rec_name = "display_name"

    partner_id = fields.Many2one(
        "res.partner", "Partner",
        ondelete="set null",
        index=True,
    )
    partner_name = fields.Char(
        "Partner Name",
        help="Stored separately in case partner is deleted.",
    )
    operation = fields.Selection(
        [
            ("auto_detect", "Auto Detect"),
            ("ai_suggest", "AI Suggestion"),
            ("manual_search", "Manual Search"),
            ("manual_select", "Manual Selection"),
            ("batch_detect", "Batch Auto-detect"),
            ("apply", "Address Applied"),
        ],
        string="Operation",
        required=True,
        index=True,
    )
    input_address = fields.Text(
        "Input Address",
        help="The raw address text that was analyzed.",
    )
    result_display = fields.Char(
        "Result",
        help="The matched or suggested address.",
    )
    confidence = fields.Float(
        "Confidence %",
        digits=(5, 1),
    )
    source = fields.Selection(
        [
            ("fuzzy", "Fuzzy Matching"),
            ("ai", "AI Suggestion"),
            ("manual", "Manual"),
            ("database", "Database Search"),
        ],
        string="Source",
    )
    province_id = fields.Many2one("vn.province", "Province")
    district_id = fields.Many2one("vn.district", "District")
    ward_id = fields.Many2one("vn.ward", "Ward")
    success = fields.Boolean("Success", default=True)
    error_message = fields.Text("Error Details")
    user_id = fields.Many2one(
        "res.users", "User",
        default=lambda self: self.env.uid,
    )
    display_name = fields.Char(
        "Display Name", compute="_compute_display_name", store=True,
    )

    @api.depends("partner_name", "operation", "create_date")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.partner_name:
                parts.append(rec.partner_name)
            if rec.operation:
                op_label = dict(
                    rec._fields["operation"].selection
                ).get(rec.operation, rec.operation)
                parts.append(op_label)
            rec.display_name = " - ".join(parts) if parts else "Log Entry"

    @api.model
    def log_operation(self, partner, operation, input_address="",
                      result_display="", confidence=0.0, source="fuzzy",
                      province_id=False, district_id=False, ward_id=False,
                      success=True, error_message=""):
        """Create a log entry for an address operation.

        This method is designed to never raise exceptions - it logs
        errors internally and returns False on failure.
        """
        try:
            vals = {
                "partner_id": partner.id if partner else False,
                "partner_name": partner.name if partner else "",
                "operation": operation,
                "input_address": (input_address or "")[:500],
                "result_display": (result_display or "")[:200],
                "confidence": confidence,
                "source": source,
                "province_id": province_id,
                "district_id": district_id,
                "ward_id": ward_id,
                "success": success,
                "error_message": (error_message or "")[:1000] if error_message else False,
            }
            record = self.sudo().create(vals)
            logger.debug(
                "Address log created: partner=%s, op=%s, success=%s",
                partner.name if partner else "N/A", operation, success,
            )
            return record
        except Exception as e:
            logger.error(
                "Failed to create address lookup log: %s", e, exc_info=True,
            )
            return False
