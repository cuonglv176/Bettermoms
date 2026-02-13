# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class AddressLookupWizard(models.TransientModel):
    _name = "address.lookup.wizard"
    _description = "Address Lookup Wizard"

    partner_id = fields.Many2one("res.partner", "Partner")

    # --- Cascading dropdown fields (offline data) ---
    province_id = fields.Many2one("vn.province", "Province/City")
    district_id = fields.Many2one(
        "vn.district", "District",
        domain="[('province_id', '=', province_id)]",
    )
    ward_id = fields.Many2one(
        "vn.ward", "Ward/Commune",
        domain="[('district_id', '=', district_id)]",
    )
    street_input = fields.Char("Street Address", help="House number and street name")

    # --- Search fields ---
    search_query = fields.Char("Search Address")
    result_line_ids = fields.One2many(
        "address.lookup.wizard.line", "wizard_id", "Results"
    )
    search_performed = fields.Boolean("Search Performed", default=False)

    @api.onchange("province_id")
    def _onchange_province_id(self):
        self.district_id = False
        self.ward_id = False

    @api.onchange("district_id")
    def _onchange_district_id(self):
        self.ward_id = False

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

    def button_apply_dropdown(self):
        """Apply address from cascading dropdowns back to the partner."""
        self.ensure_one()
        if not self.province_id:
            raise UserError(_("Please select a Province/City."))

        logger.info(
            "Applying dropdown address to partner [%s]: province=%s, district=%s, ward=%s",
            self.partner_id.id,
            self.province_id.name_with_type,
            self.district_id.name_with_type if self.district_id else "N/A",
            self.ward_id.name_with_type if self.ward_id else "N/A",
        )

        try:
            vn_id = self._get_vn_country_id()
            partner_vals = {
                "x_province_id": self.province_id.id,
                "x_district_id": self.district_id.id if self.district_id else False,
                "x_ward_id": self.ward_id.id if self.ward_id else False,
                "city": self.province_id.name,
                "x_address_verified": True,
            }
            if self.street_input:
                partner_vals["street"] = self.street_input

            # Match province to res.country.state
            state = self.env["res.country.state"].search(
                [("country_id", "=", vn_id), ("name", "ilike", self.province_id.name)],
                limit=1,
            )
            if state:
                partner_vals["state_id"] = state.id
                partner_vals["country_id"] = vn_id

            self.partner_id.write(partner_vals)
            logger.info(
                "Address applied successfully to partner [%s] %s",
                self.partner_id.id, self.partner_id.name,
            )
            return {"type": "ir.actions.act_window_close"}
        except UserError:
            raise
        except Exception as e:
            logger.error(
                "Error applying dropdown address to partner [%s]: %s",
                self.partner_id.id, e, exc_info=True,
            )
            raise UserError(
                _("Failed to apply address: %s") % str(e)
            ) from e

    def button_search(self):
        """Search address from local database."""
        self.ensure_one()
        if not self.search_query or len(self.search_query.strip()) < 2:
            raise UserError(_("Please enter at least 2 characters to search."))

        query = self.search_query.strip()
        logger.info("Address search initiated: query='%s'", query)

        results = []
        try:
            ward_results = self._search_wards_offline(query)
            results.extend(ward_results)
            logger.info("Address search '%s': found %d results", query, len(results))
        except Exception as e:
            logger.error(
                "Ward search error for query '%s': %s",
                query, e, exc_info=True,
            )
            raise UserError(
                _("Error searching address: %s") % str(e)
            ) from e

        if not results:
            logger.info("No results found for query '%s'", query)
            raise UserError(
                _("No address found for '%s'. Try a different search term.") % query
            )

        # Clear old results
        try:
            self.result_line_ids.unlink()
        except Exception as e:
            logger.warning("Could not clear old search results: %s", e)

        # Create result lines
        line_vals = []
        for idx, res in enumerate(results[:15]):
            line_vals.append((0, 0, {
                "sequence": idx,
                "description": res.get("description", ""),
                "ward_name": res.get("ward_name", ""),
                "district_name": res.get("district_name", ""),
                "province_name": res.get("province_name", ""),
                "ward_id": res.get("ward_id", False),
                "district_id": res.get("district_id", False),
                "province_id": res.get("province_id", False),
                "is_selected": idx == 0,
            }))

        self.write({
            "result_line_ids": line_vals,
            "search_performed": True,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Address Lookup"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _search_wards_offline(self, query):
        """Search wards from local database, with fuzzy fallback."""
        # Step 1: Try ilike search (fast, handles exact/substring matches)
        words = query.lower().split()
        domain = []
        for word in words:
            if len(word) >= 2:
                domain.append(("path_with_type", "ilike", word))

        if domain:
            wards = self.env["vn.ward"].search(domain, limit=15)
            if wards:
                return [{
                    "description": w.path_with_type or "",
                    "ward_name": w.name_with_type or w.name,
                    "district_name": w.district_id.name_with_type if w.district_id else "",
                    "province_name": w.province_id.name_with_type if w.province_id else "",
                    "ward_id": w.id,
                    "district_id": w.district_id.id if w.district_id else False,
                    "province_id": w.province_id.id if w.province_id else False,
                    "confidence": 100.0,
                } for w in wards]

        # Step 2: Fallback to fuzzy matching engine
        logger.info("ilike search found no results for '%s', trying fuzzy match", query)
        try:
            from ..utils.address_matcher import auto_detect_address
            fuzzy_results = auto_detect_address(query, "", "", self.env)
            return [{
                "description": r["display"],
                "ward_name": r["ward_name"],
                "district_name": r["district_name"],
                "province_name": r["province_name"],
                "ward_id": r["ward_id"],
                "district_id": r["district_id"],
                "province_id": r["province_id"],
                "confidence": round(r["confidence"] * 100, 1),
            } for r in fuzzy_results]
        except Exception as e:
            logger.warning("Fuzzy search fallback failed: %s", e)
            return []

    def button_apply_search(self):
        """Apply selected search result back to the partner."""
        self.ensure_one()
        selected = self.result_line_ids.filtered(lambda l: l.is_selected)
        if not selected:
            raise UserError(_("Please select an address from the results."))
        if len(selected) > 1:
            raise UserError(_("Please select only one address."))

        selected = selected[0]
        logger.info(
            "Applying search result to partner [%s]: %s",
            self.partner_id.id, selected.description,
        )

        try:
            vn_id = self._get_vn_country_id()
            partner_vals = {
                "x_address_verified": True,
            }

            if selected.province_id:
                partner_vals["x_province_id"] = selected.province_id.id
                partner_vals["city"] = selected.province_id.name
                # Match state_id
                state = self.env["res.country.state"].search(
                    [("country_id", "=", vn_id), ("name", "ilike", selected.province_id.name)],
                    limit=1,
                )
                if state:
                    partner_vals["state_id"] = state.id
                    partner_vals["country_id"] = vn_id

            if selected.district_id:
                partner_vals["x_district_id"] = selected.district_id.id

            if selected.ward_id:
                partner_vals["x_ward_id"] = selected.ward_id.id

            self.partner_id.write(partner_vals)
            logger.info(
                "Search result applied successfully to partner [%s] %s",
                self.partner_id.id, self.partner_id.name,
            )
            return {"type": "ir.actions.act_window_close"}
        except UserError:
            raise
        except Exception as e:
            logger.error(
                "Error applying search result to partner [%s]: %s",
                self.partner_id.id, e, exc_info=True,
            )
            raise UserError(
                _("Failed to apply address: %s") % str(e)
            ) from e


class AddressLookupWizardLine(models.TransientModel):
    _name = "address.lookup.wizard.line"
    _description = "Address Lookup Result Line"
    _order = "sequence"

    wizard_id = fields.Many2one(
        "address.lookup.wizard", "Wizard", ondelete="cascade"
    )
    sequence = fields.Integer("Sequence")
    description = fields.Char("Full Address")
    ward_name = fields.Char("Ward")
    district_name = fields.Char("District")
    province_name = fields.Char("Province")
    ward_id = fields.Many2one("vn.ward", "Ward Record")
    district_id = fields.Many2one("vn.district", "District Record")
    province_id = fields.Many2one("vn.province", "Province Record")
    confidence = fields.Float("Confidence %", digits=(5, 1), default=0.0)
    is_selected = fields.Boolean("Select", default=False)

    @api.onchange("is_selected")
    def _onchange_is_selected(self):
        """Ensure only one line is selected at a time."""
        if self.is_selected and self.wizard_id:
            for line in self.wizard_id.result_line_ids:
                if line.id != self.id and line.is_selected:
                    line.is_selected = False
