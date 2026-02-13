# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class AddressBatchWizard(models.TransientModel):
    _name = "address.batch.wizard"
    _description = "Batch Address Auto-detect"

    state = fields.Selection([
        ("draft", "Ready"),
        ("done", "Review Results"),
    ], default="draft")

    partner_count = fields.Integer("Partners to Process", readonly=True)
    line_ids = fields.One2many(
        "address.batch.wizard.line", "wizard_id", "Results",
    )

    # Summary counters
    matched_count = fields.Integer("Auto-matched", compute="_compute_counts")
    uncertain_count = fields.Integer("Needs Review", compute="_compute_counts")
    unmatched_count = fields.Integer("No Match", compute="_compute_counts")
    skipped_count = fields.Integer("Skipped", compute="_compute_counts")

    @api.depends("line_ids.status")
    def _compute_counts(self):
        for wiz in self:
            lines = wiz.line_ids
            wiz.matched_count = len(lines.filtered(lambda l: l.status == "matched"))
            wiz.uncertain_count = len(lines.filtered(lambda l: l.status == "uncertain"))
            wiz.unmatched_count = len(lines.filtered(lambda l: l.status == "unmatched"))
            wiz.skipped_count = len(lines.filtered(lambda l: l.status == "skipped"))

    def button_process(self):
        """Run auto-detect on all selected partners."""
        self.ensure_one()
        partner_ids = self.env.context.get("active_ids", [])
        if not partner_ids:
            raise UserError(_("No partners selected."))

        partners = self.env["res.partner"].browse(partner_ids)
        logger.info(
            "Batch address auto-detect started for %d partners",
            len(partners),
        )

        from ..utils.address_matcher import auto_detect_address

        lines = []
        processed = 0
        for partner in partners:
            processed += 1

            # Skip partners that already have verified addresses
            if partner.x_province_id and partner.x_address_verified:
                lines.append((0, 0, {
                    "partner_id": partner.id,
                    "status": "skipped",
                    "current_address": self._build_current_address(partner),
                    "suggested_display": _("Already verified"),
                }))
                continue

            # Skip partners with no address data
            raw = " ".join(filter(None, [
                partner.street, partner.street2, partner.city,
            ])).strip()
            if not raw:
                lines.append((0, 0, {
                    "partner_id": partner.id,
                    "status": "unmatched",
                    "current_address": "",
                    "suggested_display": _("No address data"),
                }))
                continue

            try:
                results = auto_detect_address(
                    partner.street or "",
                    partner.street2 or "",
                    partner.city or "",
                    self.env,
                )
            except Exception as e:
                logger.error(
                    "Batch auto-detect error for partner [%s] %s: %s",
                    partner.id, partner.name, e,
                )
                lines.append((0, 0, {
                    "partner_id": partner.id,
                    "status": "unmatched",
                    "current_address": self._build_current_address(partner),
                    "suggested_display": _("Error: %s") % str(e)[:100],
                }))
                continue

            if results and results[0]["confidence"] >= 0.85:
                best = results[0]
                lines.append((0, 0, {
                    "partner_id": partner.id,
                    "status": "matched",
                    "province_id": best["province_id"] or False,
                    "district_id": best["district_id"] or False,
                    "ward_id": best["ward_id"] or False,
                    "confidence": round(best["confidence"] * 100, 1),
                    "current_address": self._build_current_address(partner),
                    "suggested_display": best["display"],
                    "apply": True,
                }))
            elif results:
                best = results[0]
                lines.append((0, 0, {
                    "partner_id": partner.id,
                    "status": "uncertain",
                    "province_id": best["province_id"] or False,
                    "district_id": best["district_id"] or False,
                    "ward_id": best["ward_id"] or False,
                    "confidence": round(best["confidence"] * 100, 1),
                    "current_address": self._build_current_address(partner),
                    "suggested_display": best["display"],
                    "apply": False,
                }))
            else:
                lines.append((0, 0, {
                    "partner_id": partner.id,
                    "status": "unmatched",
                    "current_address": self._build_current_address(partner),
                }))

        self.write({"line_ids": lines, "state": "done"})
        logger.info(
            "Batch auto-detect completed: %d processed", processed,
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Batch Address Auto-detect"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _build_current_address(self, partner):
        """Build current address string for display."""
        parts = filter(None, [
            partner.street, partner.street2, partner.city,
        ])
        return ", ".join(parts)[:200]

    def button_apply(self):
        """Apply all checked results to their partners."""
        self.ensure_one()
        to_apply = self.line_ids.filtered(lambda l: l.apply and l.province_id)

        if not to_apply:
            raise UserError(_("No results selected to apply."))

        applied = 0
        errors = 0
        vn_id = self.env["res.partner"]._get_vn_country_id()

        for line in to_apply:
            try:
                vals = {
                    "x_province_id": line.province_id.id,
                    "x_district_id": line.district_id.id if line.district_id else False,
                    "x_ward_id": line.ward_id.id if line.ward_id else False,
                    "x_address_verified": True,
                    "city": line.province_id.name,
                }
                # Match province to state
                state = self.env["res.country.state"].search(
                    [("country_id", "=", vn_id),
                     ("name", "ilike", line.province_id.name)],
                    limit=1,
                )
                if state:
                    vals["state_id"] = state.id
                    vals["country_id"] = vn_id

                line.partner_id.write(vals)
                applied += 1
            except Exception as e:
                logger.error(
                    "Failed to apply batch address to partner [%s]: %s",
                    line.partner_id.id, e,
                )
                errors += 1

        logger.info(
            "Batch address apply: %d applied, %d errors", applied, errors,
        )

        if errors:
            raise UserError(
                _("Applied %d addresses. %d failed - check server logs for details.")
                % (applied, errors)
            )

        return {"type": "ir.actions.act_window_close"}


class AddressBatchWizardLine(models.TransientModel):
    _name = "address.batch.wizard.line"
    _description = "Batch Address Result Line"
    _order = "status, confidence desc"

    wizard_id = fields.Many2one(
        "address.batch.wizard", "Wizard", ondelete="cascade",
    )
    partner_id = fields.Many2one("res.partner", "Partner", readonly=True)
    partner_name = fields.Char(
        "Partner Name", related="partner_id.name", readonly=True,
    )
    current_address = fields.Char("Current Address", readonly=True)

    status = fields.Selection([
        ("matched", "Matched"),
        ("uncertain", "Needs Review"),
        ("unmatched", "No Match"),
        ("skipped", "Skipped"),
    ], string="Status", readonly=True)

    province_id = fields.Many2one("vn.province", "Suggested Province")
    district_id = fields.Many2one("vn.district", "Suggested District")
    ward_id = fields.Many2one("vn.ward", "Suggested Ward")
    confidence = fields.Float("Confidence %", digits=(5, 1), readonly=True)
    suggested_display = fields.Char("Suggested Address", readonly=True)
    apply = fields.Boolean("Apply", default=False)
