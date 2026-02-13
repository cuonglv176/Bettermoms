# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

logger = logging.getLogger(__name__)


class VnProvince(models.Model):
    _name = "vn.province"
    _description = "Vietnam Province / City"
    _order = "name"

    name = fields.Char("Name", required=True, index=True)
    name_with_type = fields.Char("Full Name", index=True)
    code = fields.Char("Code", required=True, index=True)
    slug = fields.Char("Slug")
    type = fields.Char("Type")

    district_ids = fields.One2many("vn.district", "province_id", "Districts")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Province code must be unique!"),
    ]

    def name_get(self):
        return [(rec.id, rec.name_with_type or rec.name) for rec in self]


class VnDistrict(models.Model):
    _name = "vn.district"
    _description = "Vietnam District"
    _order = "name"

    name = fields.Char("Name", required=True, index=True)
    name_with_type = fields.Char("Full Name", index=True)
    code = fields.Char("Code", required=True, index=True)
    slug = fields.Char("Slug")
    type = fields.Char("Type")
    province_id = fields.Many2one("vn.province", "Province", ondelete="cascade", index=True)

    ward_ids = fields.One2many("vn.ward", "district_id", "Wards")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "District code must be unique!"),
    ]

    def name_get(self):
        return [(rec.id, rec.name_with_type or rec.name) for rec in self]


class VnWard(models.Model):
    _name = "vn.ward"
    _description = "Vietnam Ward / Commune"
    _order = "name"

    name = fields.Char("Name", required=True, index=True)
    name_with_type = fields.Char("Full Name", index=True)
    code = fields.Char("Code", required=True, index=True)
    slug = fields.Char("Slug")
    type = fields.Char("Type")
    district_id = fields.Many2one("vn.district", "District", ondelete="cascade", index=True)
    province_id = fields.Many2one(
        "vn.province", "Province", related="district_id.province_id", store=True
    )
    path_with_type = fields.Char("Full Path")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Ward code must be unique!"),
    ]

    def name_get(self):
        return [(rec.id, rec.name_with_type or rec.name) for rec in self]

    @api.model
    def search_address_autocomplete(self, query):
        """Search wards by path_with_type for address lookup.

        Args:
            query (str): User search text, e.g. "Ba Dinh Ha Noi"

        Returns:
            list[dict]: Up to 10 results with ward/district/province info.
        """
        if not query or len(query.strip()) < 2:
            return []

        try:
            words = query.strip().lower().split()
            domain = []
            for word in words:
                if len(word) >= 2:
                    domain.append(("path_with_type", "ilike", word))

            if not domain:
                return []

            wards = self.search(domain, limit=10)
            logger.debug(
                "Address autocomplete search '%s': found %d results",
                query, len(wards),
            )
            return [{
                "ward_id": w.id,
                "district_id": w.district_id.id if w.district_id else False,
                "province_id": w.province_id.id if w.province_id else False,
                "display": w.path_with_type or "",
                "ward_name": w.name_with_type or w.name,
                "district_name": (
                    w.district_id.name_with_type or w.district_id.name
                ) if w.district_id else "",
                "province_name": (
                    w.province_id.name_with_type or w.province_id.name
                ) if w.province_id else "",
            } for w in wards]
        except Exception as e:
            logger.error(
                "Error in address autocomplete search for query '%s': %s",
                query, e, exc_info=True,
            )
            return []
