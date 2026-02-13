# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_province_id = fields.Many2one(
        "vn.province", "Province/City",
        help="Tinh/Thanh pho",
    )
    x_district_id = fields.Many2one(
        "vn.district", "District",
        help="Quan/Huyen",
        domain="[('province_id', '=', x_province_id)]",
    )
    x_ward_id = fields.Many2one(
        "vn.ward", "Ward/Commune",
        help="Phuong/Xa",
        domain="[('district_id', '=', x_district_id)]",
    )
    x_address_verified = fields.Boolean(
        "Address Verified",
        default=False,
        help="True if address was verified via address lookup",
    )

    def _get_vn_country_id(self):
        """Get Vietnam country record ID safely."""
        try:
            return self.env.ref("base.vn").id
        except ValueError:
            logger.warning("Could not find base.vn external ID, using fallback ID=241")
            return 241
        except Exception as e:
            logger.error("Unexpected error fetching VN country ID: %s", e)
            return 241

    @api.onchange("x_province_id")
    def _onchange_province_id(self):
        """Clear district and ward when province changes, auto-fill city."""
        self.x_district_id = False
        self.x_ward_id = False
        if self.x_province_id:
            self.city = self.x_province_id.name
            try:
                vn_id = self._get_vn_country_id()
                state = self.env["res.country.state"].search(
                    [("country_id", "=", vn_id), ("name", "ilike", self.x_province_id.name)],
                    limit=1,
                )
                if state:
                    self.state_id = state.id
                    self.country_id = vn_id
            except Exception as e:
                logger.warning(
                    "Could not match province '%s' to country state: %s",
                    self.x_province_id.name, e,
                )

    @api.onchange("x_district_id")
    def _onchange_district_id(self):
        """Clear ward when district changes."""
        self.x_ward_id = False

    def button_verify_address(self):
        """Open the address lookup wizard pre-filled with current address."""
        self.ensure_one()
        logger.info(
            "Opening address lookup wizard for partner [%s] %s",
            self.id, self.name,
        )
        try:
            parts = [
                self.street or "",
                self.x_ward_id.name_with_type if self.x_ward_id else "",
                self.x_district_id.name_with_type if self.x_district_id else "",
                self.x_province_id.name_with_type if self.x_province_id else "",
            ]
            initial_query = ", ".join([p for p in parts if p.strip()])

            return {
                "type": "ir.actions.act_window",
                "name": _("Address Lookup"),
                "res_model": "address.lookup.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_partner_id": self.id,
                    "default_search_query": initial_query,
                    "default_province_id": self.x_province_id.id if self.x_province_id else False,
                    "default_district_id": self.x_district_id.id if self.x_district_id else False,
                    "default_ward_id": self.x_ward_id.id if self.x_ward_id else False,
                },
            }
        except Exception as e:
            logger.error(
                "Error opening address lookup wizard for partner [%s]: %s",
                self.id, e, exc_info=True,
            )
            raise UserError(
                _("Could not open address lookup: %s") % str(e)
            ) from e

    def button_auto_detect_address(self):
        """Auto-detect province/district/ward from street, street2, city text.

        Uses a two-stage approach:
        1. Fuzzy matching engine (fast, offline)
        2. AI suggestion fallback (if fuzzy match confidence is low)
        """
        self.ensure_one()
        from ..utils.address_matcher import auto_detect_address
        from ..utils.ai_address_suggest import ai_suggest_address, ai_match_to_db

        raw_address = ", ".join(filter(None, [
            self.street or "", self.street2 or "", self.city or "",
        ]))

        logger.info(
            "Auto-detecting address for partner [%s] %s: street='%s', city='%s'",
            self.id, self.name, self.street or "", self.city or "",
        )

        log_model = self.env["address.lookup.log"]

        # Stage 1: Fuzzy matching
        try:
            results = auto_detect_address(
                self.street or "",
                self.street2 or "",
                self.city or "",
                self.env,
            )
        except Exception as e:
            logger.error(
                "Error in auto-detect address for partner [%s]: %s",
                self.id, e, exc_info=True,
            )
            log_model.log_operation(
                partner=self,
                operation="auto_detect",
                input_address=raw_address,
                source="fuzzy",
                success=False,
                error_message=str(e),
            )
            raise UserError(
                _("Address auto-detection failed: %s") % str(e)
            ) from e

        # Stage 2: AI suggestion fallback
        ai_results = []
        if not results or (results and results[0]["confidence"] < 0.70):
            logger.info(
                "Fuzzy match low confidence (%.0f%%) for partner [%s], trying AI suggestion",
                results[0]["confidence"] * 100 if results else 0,
                self.id,
            )
            try:
                ai_result = ai_suggest_address(raw_address, self.env)
                if ai_result:
                    ai_results = ai_match_to_db(ai_result, self.env)
                    if ai_results:
                        logger.info(
                            "AI suggestion found %d results for partner [%s], best='%s' (%.0f%%)",
                            len(ai_results), self.id,
                            ai_results[0]["display"],
                            ai_results[0]["confidence"] * 100,
                        )
                        log_model.log_operation(
                            partner=self,
                            operation="ai_suggest",
                            input_address=raw_address,
                            result_display=ai_results[0]["display"],
                            confidence=ai_results[0]["confidence"] * 100,
                            source="ai",
                            province_id=ai_results[0].get("province_id"),
                            district_id=ai_results[0].get("district_id"),
                            ward_id=ai_results[0].get("ward_id"),
                            success=True,
                        )
            except Exception as e:
                logger.warning(
                    "AI address suggestion failed for partner [%s]: %s",
                    self.id, e,
                )
                log_model.log_operation(
                    partner=self,
                    operation="ai_suggest",
                    input_address=raw_address,
                    source="ai",
                    success=False,
                    error_message=str(e),
                )

        # Merge results: AI results first if they have higher confidence
        all_results = []
        seen_keys = set()
        for r in (ai_results + results):
            key = (r.get("province_id"), r.get("district_id"), r.get("ward_id"))
            if key not in seen_keys:
                seen_keys.add(key)
                all_results.append(r)
        all_results.sort(key=lambda r: -r.get("confidence", 0))
        all_results = all_results[:5]

        if not all_results:
            log_model.log_operation(
                partner=self,
                operation="auto_detect",
                input_address=raw_address,
                source="fuzzy",
                success=False,
                error_message="No results found",
            )
            raise UserError(
                _("Could not detect address from current data.\n"
                  "Please use the 'Address Lookup' button for manual search.")
            )

        # Log the auto-detect operation
        best = all_results[0]
        log_model.log_operation(
            partner=self,
            operation="auto_detect",
            input_address=raw_address,
            result_display=best.get("display", ""),
            confidence=best.get("confidence", 0) * 100,
            source=best.get("source", "fuzzy"),
            province_id=best.get("province_id"),
            district_id=best.get("district_id"),
            ward_id=best.get("ward_id"),
            success=True,
        )

        if best["confidence"] >= 0.85:
            return self._apply_and_confirm_auto_detect(best, all_results)
        else:
            return self._show_auto_detect_choices(all_results)

    def _apply_and_confirm_auto_detect(self, best, all_results):
        """Apply best result and open wizard for user confirmation."""
        self.ensure_one()
        vn_id = self._get_vn_country_id()

        # Write the best match
        vals = {
            "x_province_id": best["province_id"] or False,
            "x_district_id": best["district_id"] or False,
            "x_ward_id": best["ward_id"] or False,
            "x_address_verified": True,
        }

        if best["province_id"]:
            try:
                province = self.env["vn.province"].browse(best["province_id"])
                vals["city"] = province.name
                state = self.env["res.country.state"].search(
                    [("country_id", "=", vn_id), ("name", "ilike", province.name)],
                    limit=1,
                )
                if state:
                    vals["state_id"] = state.id
                    vals["country_id"] = vn_id
            except Exception as e:
                logger.warning(
                    "Error resolving province for partner [%s]: %s",
                    self.id, e,
                )

        try:
            self.write(vals)
            logger.info(
                "Auto-detect applied to partner [%s] %s: %s (%.0f%%)",
                self.id, self.name, best["display"], best["confidence"] * 100,
            )

            # Log the apply operation
            self.env["address.lookup.log"].log_operation(
                partner=self,
                operation="apply",
                input_address=best.get("display", ""),
                result_display=best.get("display", ""),
                confidence=best.get("confidence", 0) * 100,
                source=best.get("source", "fuzzy"),
                province_id=best.get("province_id"),
                district_id=best.get("district_id"),
                ward_id=best.get("ward_id"),
                success=True,
            )
        except Exception as e:
            logger.error(
                "Error applying auto-detect result to partner [%s]: %s",
                self.id, e, exc_info=True,
            )
            raise UserError(
                _("Failed to apply address: %s") % str(e)
            ) from e

        # Open wizard pre-populated so user can verify or adjust
        return self._open_wizard_with_results(all_results)

    def _show_auto_detect_choices(self, results):
        """Open wizard with auto-detect results for user to choose."""
        self.ensure_one()
        logger.info(
            "Showing %d auto-detect choices for partner [%s] %s (best=%.0f%%)",
            len(results), self.id, self.name,
            results[0]["confidence"] * 100 if results else 0,
        )
        return self._open_wizard_with_results(results)

    def _open_wizard_with_results(self, results):
        """Open address lookup wizard with pre-populated results."""
        self.ensure_one()

        # Build result lines for the wizard
        line_vals = []
        for idx, r in enumerate(results):
            line_vals.append((0, 0, {
                "sequence": idx,
                "description": r.get("display", ""),
                "ward_name": r.get("ward_name", ""),
                "district_name": r.get("district_name", ""),
                "province_name": r.get("province_name", ""),
                "ward_id": r.get("ward_id") or False,
                "district_id": r.get("district_id") or False,
                "province_id": r.get("province_id") or False,
                "confidence": round(r.get("confidence", 0) * 100, 1),
                "is_selected": idx == 0,
                "source": r.get("source", "fuzzy"),
            }))

        try:
            wizard = self.env["address.lookup.wizard"].create({
                "partner_id": self.id,
                "search_query": "%s, %s" % (self.street or "", self.city or ""),
                "province_id": results[0]["province_id"] or False if results else False,
                "district_id": results[0]["district_id"] or False if results else False,
                "ward_id": results[0]["ward_id"] or False if results else False,
                "result_line_ids": line_vals,
                "search_performed": True,
            })
        except Exception as e:
            logger.error(
                "Error creating address lookup wizard for partner [%s]: %s",
                self.id, e, exc_info=True,
            )
            raise UserError(
                _("Could not open address wizard: %s") % str(e)
            ) from e

        return {
            "type": "ir.actions.act_window",
            "name": _("Auto-detected Address - Please Confirm"),
            "res_model": "address.lookup.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
