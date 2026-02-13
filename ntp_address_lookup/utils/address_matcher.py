# -*- coding: utf-8 -*-
"""
Vietnamese Address Auto-Matching Engine
=======================================
Analyzes free-text address fields (street, street2, city) and matches them
against offline Province/District/Ward data using:
  - Text normalization (strip Vietnamese diacritics)
  - Type prefix detection (tp, q, p, h, x, tx, tt)
  - Alias dictionary for common abbreviations
  - Fuzzy matching via difflib.SequenceMatcher
  - Hierarchical scoring (Province -> District -> Ward)

No external dependencies required - uses Python stdlib only.
"""

import logging
import re
from collections import namedtuple
from difflib import SequenceMatcher

from .normalize import normalize_string

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

ProvinceEntry = namedtuple("ProvinceEntry", [
    "id", "name", "name_normalized", "name_with_type_normalized",
    "slug", "type", "aliases",
])

DistrictEntry = namedtuple("DistrictEntry", [
    "id", "province_id", "name", "name_normalized",
    "name_with_type_normalized", "slug", "type",
])

WardEntry = namedtuple("WardEntry", [
    "id", "district_id", "province_id", "name", "name_normalized",
    "name_with_type_normalized", "slug", "path_normalized",
    "path_with_type",
])

MatchResult = namedtuple("MatchResult", [
    "province_id", "district_id", "ward_id",
    "province_name", "district_name", "ward_name",
    "confidence", "display",
])

ParsedAddress = namedtuple("ParsedAddress", [
    "province_hints", "district_hints", "ward_hints",
    "street_parts", "raw_normalized",
])

# ---------------------------------------------------------------------------
# Common Abbreviation Aliases (normalized, lowercase)
# ---------------------------------------------------------------------------

PROVINCE_ALIASES = {
    # Ho Chi Minh City
    "tp hcm": "ho chi minh",
    "tp.hcm": "ho chi minh",
    "tphcm": "ho chi minh",
    "tp. hcm": "ho chi minh",
    "tp ho chi minh": "ho chi minh",
    "tp. ho chi minh": "ho chi minh",
    "hcm": "ho chi minh",
    "sai gon": "ho chi minh",
    "sg": "ho chi minh",
    "saigon": "ho chi minh",
    # Hanoi
    "ha noi": "ha noi",
    "hn": "ha noi",
    "hanoi": "ha noi",
    # Da Nang
    "da nang": "da nang",
    "dn": "da nang",
    "danang": "da nang",
    # Can Tho
    "can tho": "can tho",
    "ct": "can tho",
    # Hai Phong
    "hai phong": "hai phong",
    "hp": "hai phong",
    # Binh Duong
    "binh duong": "binh duong",
    "bd": "binh duong",
    # Dong Nai
    "dong nai": "dong nai",
    # Long An
    "long an": "long an",
    "la": "long an",
    # Bac Ninh
    "bac ninh": "bac ninh",
    "bn": "bac ninh",
}

# Type prefix patterns for segment identification
# Regex pattern: prefix (with optional dot) followed by content
_PREFIX_PATTERN = re.compile(
    r'^(tp|t\.p|t\.p\.|thanh pho|'
    r'q|q\.|quan|'
    r'h|h\.|huyen|'
    r'p|p\.|phuong|'
    r'x|x\.|xa|'
    r'tx|tx\.|thi xa|'
    r'tt|tt\.|thi tran)\s*\.?\s*(.+)$',
    re.IGNORECASE
)

_PREFIX_TO_LEVEL = {
    "tp": "province", "t.p": "province", "t.p.": "province",
    "thanh pho": "province",
    "q": "district", "q.": "district", "quan": "district",
    "h": "district", "h.": "district", "huyen": "district",
    "tx": "district", "tx.": "district", "thi xa": "district",
    "p": "ward", "p.": "ward", "phuong": "ward",
    "x": "ward", "x.": "ward", "xa": "ward",
    "tt": "ward", "tt.": "ward", "thi tran": "ward",
}

# Scoring weights
PROVINCE_WEIGHT = 0.3
DISTRICT_WEIGHT = 0.3
WARD_WEIGHT = 0.4

# Confidence thresholds
HIGH_CONFIDENCE = 0.85
PROVINCE_FUZZY_MIN = 0.65
DISTRICT_FUZZY_MIN = 0.60
WARD_FUZZY_MIN = 0.55

# ---------------------------------------------------------------------------
# In-Memory Cache
# ---------------------------------------------------------------------------

_CACHE = {
    "provinces": None,
    "districts": None,
    "wards": None,
    "province_by_id": None,
    "districts_by_province": None,
    "wards_by_district": None,
    "built": False,
}


def clear_cache():
    """Clear the in-memory address cache. Call when address data is reloaded."""
    _CACHE["provinces"] = None
    _CACHE["districts"] = None
    _CACHE["wards"] = None
    _CACHE["province_by_id"] = None
    _CACHE["districts_by_province"] = None
    _CACHE["wards_by_district"] = None
    _CACHE["built"] = False
    logger.info("Address matcher cache cleared")


def _ensure_cache(env):
    """Build lookup tables from DB if not yet cached."""
    if _CACHE["built"]:
        return

    logger.info("Building address matcher cache...")

    # --- Provinces ---
    prov_records = env["vn.province"].sudo().search_read(
        [], ["id", "name", "name_with_type", "slug", "type"],
    )
    provinces = []
    province_by_id = {}
    for p in prov_records:
        name_norm = normalize_string(p["name"] or "").lower().strip()
        nwt_norm = normalize_string(p["name_with_type"] or p["name"] or "").lower().strip()
        slug = (p["slug"] or "").lower().strip()

        # Build aliases for this province
        aliases = set()
        aliases.add(name_norm)
        if slug:
            aliases.add(slug)
            aliases.add(slug.replace("-", " "))
        # Add known aliases from PROVINCE_ALIASES that map to this name
        for alias_key, alias_val in PROVINCE_ALIASES.items():
            if alias_val == name_norm:
                aliases.add(alias_key)

        entry = ProvinceEntry(
            id=p["id"],
            name=p["name_with_type"] or p["name"],
            name_normalized=name_norm,
            name_with_type_normalized=nwt_norm,
            slug=slug,
            type=(p["type"] or "").lower(),
            aliases=aliases,
        )
        provinces.append(entry)
        province_by_id[p["id"]] = entry

    _CACHE["provinces"] = provinces
    _CACHE["province_by_id"] = province_by_id

    # --- Districts ---
    dist_records = env["vn.district"].sudo().search_read(
        [], ["id", "name", "name_with_type", "slug", "type", "province_id"],
    )
    districts = []
    districts_by_province = {}
    for d in dist_records:
        prov_id = d["province_id"][0] if d["province_id"] else None
        name_norm = normalize_string(d["name"] or "").lower().strip()
        nwt_norm = normalize_string(d["name_with_type"] or d["name"] or "").lower().strip()
        slug = (d["slug"] or "").lower().strip()

        entry = DistrictEntry(
            id=d["id"],
            province_id=prov_id,
            name=d["name_with_type"] or d["name"],
            name_normalized=name_norm,
            name_with_type_normalized=nwt_norm,
            slug=slug,
            type=(d["type"] or "").lower(),
        )
        districts.append(entry)
        districts_by_province.setdefault(prov_id, []).append(entry)

    _CACHE["districts"] = districts
    _CACHE["districts_by_province"] = districts_by_province

    # --- Wards ---
    ward_records = env["vn.ward"].sudo().search_read(
        [], ["id", "name", "name_with_type", "slug", "type",
             "district_id", "province_id", "path_with_type"],
    )
    wards = []
    wards_by_district = {}
    for w in ward_records:
        dist_id = w["district_id"][0] if w["district_id"] else None
        prov_id = w["province_id"][0] if w["province_id"] else None
        name_norm = normalize_string(w["name"] or "").lower().strip()
        nwt_norm = normalize_string(w["name_with_type"] or w["name"] or "").lower().strip()
        slug = (w["slug"] or "").lower().strip()
        path_norm = normalize_string(w["path_with_type"] or "").lower().strip()

        entry = WardEntry(
            id=w["id"],
            district_id=dist_id,
            province_id=prov_id,
            name=w["name_with_type"] or w["name"],
            name_normalized=name_norm,
            name_with_type_normalized=nwt_norm,
            slug=slug,
            path_normalized=path_norm,
            path_with_type=w["path_with_type"] or "",
        )
        wards.append(entry)
        wards_by_district.setdefault(dist_id, []).append(entry)

    _CACHE["wards"] = wards
    _CACHE["wards_by_district"] = wards_by_district
    _CACHE["built"] = True

    logger.info(
        "Address matcher cache built: %d provinces, %d districts, %d wards",
        len(provinces), len(districts), len(wards),
    )


# ---------------------------------------------------------------------------
# Address Parser
# ---------------------------------------------------------------------------

def _identify_segment(segment):
    """Identify an address segment by its type prefix.

    Returns:
        tuple: (level, cleaned_name) where level is "province", "district",
               "ward", or "unknown".
    """
    segment = segment.strip()
    if not segment:
        return ("unknown", segment)

    # Check province aliases first (handles "hcm", "tp hcm", "sg", etc.)
    seg_lower = segment.lower()
    if seg_lower in PROVINCE_ALIASES:
        return ("province", PROVINCE_ALIASES[seg_lower])

    # Try prefix pattern matching
    match = _PREFIX_PATTERN.match(seg_lower)
    if match:
        prefix = match.group(1).strip().rstrip(".")
        rest = match.group(2).strip()
        level = _PREFIX_TO_LEVEL.get(prefix, "unknown")
        if level != "unknown" and rest:
            return (level, rest)

    # Starts with digit? Likely street number
    if re.match(r'^\d', segment):
        return ("unknown", segment)

    return ("unknown", segment)


def _parse_address(street, street2, city):
    """Parse address fields into structured hints.

    Vietnamese addresses commonly follow: street, ward, district, province
    """
    # Combine all address text
    parts = []
    for text in [street, street2, city]:
        if text and text.strip():
            parts.append(text.strip())

    raw_text = ", ".join(parts)
    if not raw_text.strip():
        return None

    # Normalize
    raw_normalized = normalize_string(raw_text).lower().strip()

    # Split by comma
    if "," in raw_text:
        segments = [s.strip() for s in raw_text.split(",") if s.strip()]
    else:
        # Try splitting by " - " as alternative separator
        if " - " in raw_text:
            segments = [s.strip() for s in raw_text.split(" - ") if s.strip()]
        else:
            segments = [raw_text.strip()]

    # Normalize each segment
    norm_segments = [normalize_string(s).lower().strip() for s in segments]

    # Identify each segment
    province_hints = []
    district_hints = []
    ward_hints = []
    street_parts = []

    for seg in norm_segments:
        level, name = _identify_segment(seg)
        if level == "province":
            province_hints.append(name)
        elif level == "district":
            district_hints.append(name)
        elif level == "ward":
            ward_hints.append(name)
        else:
            street_parts.append(seg)

    # If no tagged segments found and we have multiple segments,
    # apply reverse-order heuristic: last=province, 2nd last=district, 3rd last=ward
    if not province_hints and not district_hints and not ward_hints:
        if len(norm_segments) >= 3:
            # Last segment is likely province
            province_hints.append(norm_segments[-1])
            # Second to last is likely district
            district_hints.append(norm_segments[-2])
            # Third to last is likely ward
            ward_hints.append(norm_segments[-3])
            # Remaining are street parts
            street_parts = norm_segments[:-3]
        elif len(norm_segments) == 2:
            # Could be "district, province" or "ward, province"
            province_hints.append(norm_segments[-1])
            district_hints.append(norm_segments[-2])

    return ParsedAddress(
        province_hints=province_hints,
        district_hints=district_hints,
        ward_hints=ward_hints,
        street_parts=street_parts,
        raw_normalized=raw_normalized,
    )


# ---------------------------------------------------------------------------
# Matching Functions
# ---------------------------------------------------------------------------

def _fuzzy_ratio(a, b):
    """Compute similarity ratio between two strings using SequenceMatcher."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _match_provinces(parsed, provinces):
    """Match province hints against province entries.

    Returns:
        list of (ProvinceEntry, score) tuples, sorted by score descending.
    """
    candidates = []
    seen_ids = set()

    for hint in parsed.province_hints:
        hint = hint.strip()
        if not hint:
            continue

        for p in provinces:
            if p.id in seen_ids:
                continue

            # Exact match on normalized name
            if hint == p.name_normalized:
                candidates.append((p, 1.0))
                seen_ids.add(p.id)
                continue

            # Alias match
            if hint in p.aliases:
                candidates.append((p, 0.98))
                seen_ids.add(p.id)
                continue

            # Slug match
            hint_slug = hint.replace(" ", "-")
            if hint_slug == p.slug:
                candidates.append((p, 0.97))
                seen_ids.add(p.id)
                continue

            # Contained in name_with_type_normalized
            if hint in p.name_with_type_normalized or p.name_normalized in hint:
                candidates.append((p, 0.90))
                seen_ids.add(p.id)
                continue

            # Fuzzy match
            ratio = _fuzzy_ratio(hint, p.name_normalized)
            if ratio >= PROVINCE_FUZZY_MIN:
                candidates.append((p, ratio))
                seen_ids.add(p.id)

    # If no hints matched, try substring matching against full raw text
    if not candidates:
        for p in provinces:
            if p.id in seen_ids:
                continue
            if p.name_normalized in parsed.raw_normalized:
                candidates.append((p, 0.85))
                seen_ids.add(p.id)
            elif len(p.name_normalized) > 3:
                # Check raw text contains province name
                ratio = _fuzzy_ratio(p.name_normalized, parsed.raw_normalized)
                # Only if the province name appears as significant part of raw text
                if ratio >= 0.4 and p.name_normalized in parsed.raw_normalized:
                    candidates.append((p, 0.80))
                    seen_ids.add(p.id)

    candidates.sort(key=lambda x: -x[1])
    return candidates[:3]


def _match_districts(parsed, districts_for_province):
    """Match district hints against district entries for a given province.

    Returns:
        list of (DistrictEntry, score) tuples, sorted by score descending.
    """
    candidates = []
    seen_ids = set()

    for hint in parsed.district_hints:
        hint = hint.strip()
        if not hint:
            continue

        for d in districts_for_province:
            if d.id in seen_ids:
                continue

            # Exact match
            if hint == d.name_normalized:
                candidates.append((d, 1.0))
                seen_ids.add(d.id)
                continue

            # Slug match
            hint_slug = hint.replace(" ", "-")
            if hint_slug == d.slug:
                candidates.append((d, 0.97))
                seen_ids.add(d.id)
                continue

            # Handle numeric district: "1" should match "1" in name
            if hint.isdigit() and d.name_normalized == hint:
                candidates.append((d, 1.0))
                seen_ids.add(d.id)
                continue

            # Contained check
            if hint in d.name_with_type_normalized or d.name_normalized in hint:
                candidates.append((d, 0.90))
                seen_ids.add(d.id)
                continue

            # Fuzzy match
            ratio = _fuzzy_ratio(hint, d.name_normalized)
            if ratio >= DISTRICT_FUZZY_MIN:
                candidates.append((d, ratio))
                seen_ids.add(d.id)

    # Fallback: substring match in raw text
    if not candidates:
        for d in districts_for_province:
            if d.id in seen_ids:
                continue
            if d.name_normalized in parsed.raw_normalized:
                candidates.append((d, 0.80))
                seen_ids.add(d.id)

    candidates.sort(key=lambda x: -x[1])
    return candidates[:3]


def _match_wards(parsed, wards_for_district):
    """Match ward hints against ward entries for a given district.

    Returns:
        list of (WardEntry, score) tuples, sorted by score descending.
    """
    candidates = []
    seen_ids = set()

    for hint in parsed.ward_hints:
        hint = hint.strip()
        if not hint:
            continue

        for w in wards_for_district:
            if w.id in seen_ids:
                continue

            # Exact match
            if hint == w.name_normalized:
                candidates.append((w, 1.0))
                seen_ids.add(w.id)
                continue

            # Slug match
            hint_slug = hint.replace(" ", "-")
            if hint_slug == w.slug:
                candidates.append((w, 0.97))
                seen_ids.add(w.id)
                continue

            # Numeric ward: "5" matches ward named "5"
            if hint.isdigit() and w.name_normalized == hint:
                candidates.append((w, 1.0))
                seen_ids.add(w.id)
                continue

            # Contained check
            if hint in w.name_with_type_normalized or w.name_normalized in hint:
                candidates.append((w, 0.88))
                seen_ids.add(w.id)
                continue

            # Fuzzy match
            ratio = _fuzzy_ratio(hint, w.name_normalized)
            if ratio >= WARD_FUZZY_MIN:
                candidates.append((w, ratio))
                seen_ids.add(w.id)

    # Fallback: substring match in raw text
    if not candidates:
        for w in wards_for_district:
            if w.id in seen_ids:
                continue
            if len(w.name_normalized) >= 3 and w.name_normalized in parsed.raw_normalized:
                candidates.append((w, 0.75))
                seen_ids.add(w.id)

    candidates.sort(key=lambda x: -x[1])
    return candidates[:3]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def auto_detect_address(street, street2, city, env):
    """Analyze free-text address fields and return ranked match results.

    Args:
        street (str): Partner's street field (may be None/empty).
        street2 (str): Partner's street2 field (may be None/empty).
        city (str): Partner's city field (may be None/empty).
        env: Odoo environment for DB queries (used only for cache building).

    Returns:
        list[dict]: Up to 5 results, each containing:
            - province_id (int or False)
            - district_id (int or False)
            - ward_id (int or False)
            - province_name (str)
            - district_name (str)
            - ward_name (str)
            - confidence (float 0.0-1.0)
            - display (str): Full path for display
    """
    try:
        _ensure_cache(env)
    except Exception as e:
        logger.error("Failed to build address matcher cache: %s", e, exc_info=True)
        return []

    parsed = _parse_address(street or "", street2 or "", city or "")
    if not parsed:
        return []

    logger.debug(
        "Parsed address: province_hints=%s, district_hints=%s, ward_hints=%s",
        parsed.province_hints, parsed.district_hints, parsed.ward_hints,
    )

    results = []
    seen_keys = set()

    # Match provinces
    province_matches = _match_provinces(parsed, _CACHE["provinces"])

    if not province_matches:
        logger.debug("No province match found for: %s", parsed.raw_normalized)
        return []

    for prov, prov_score in province_matches:
        # Get districts for this province
        prov_districts = _CACHE["districts_by_province"].get(prov.id, [])

        district_matches = _match_districts(parsed, prov_districts)

        if not district_matches:
            # Province-only result (no district match)
            key = (prov.id, None, None)
            if key not in seen_keys:
                seen_keys.add(key)
                results.append({
                    "province_id": prov.id,
                    "district_id": False,
                    "ward_id": False,
                    "province_name": prov.name,
                    "district_name": "",
                    "ward_name": "",
                    "confidence": round(prov_score * 0.45, 4),
                    "display": prov.name,
                })
            continue

        for dist, dist_score in district_matches:
            # Get wards for this district
            dist_wards = _CACHE["wards_by_district"].get(dist.id, [])

            ward_matches = _match_wards(parsed, dist_wards)

            if ward_matches:
                for ward, ward_score in ward_matches[:2]:
                    key = (prov.id, dist.id, ward.id)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        combined = (
                            prov_score * PROVINCE_WEIGHT
                            + dist_score * DISTRICT_WEIGHT
                            + ward_score * WARD_WEIGHT
                        )
                        results.append({
                            "province_id": prov.id,
                            "district_id": dist.id,
                            "ward_id": ward.id,
                            "province_name": prov.name,
                            "district_name": dist.name,
                            "ward_name": ward.name,
                            "confidence": round(combined, 4),
                            "display": ward.path_with_type,
                        })
            else:
                # Province + District only (no ward match)
                key = (prov.id, dist.id, None)
                if key not in seen_keys:
                    seen_keys.add(key)
                    combined = (
                        prov_score * 0.45 + dist_score * 0.55
                    ) * 0.7  # Penalty for missing ward
                    results.append({
                        "province_id": prov.id,
                        "district_id": dist.id,
                        "ward_id": False,
                        "province_name": prov.name,
                        "district_name": dist.name,
                        "ward_name": "",
                        "confidence": round(combined, 4),
                        "display": "%s, %s" % (dist.name, prov.name),
                    })

    # Sort by confidence descending
    results.sort(key=lambda r: -r["confidence"])

    # Return top 5
    results = results[:5]

    if results:
        logger.info(
            "Auto-detect address: input='%s' | best match='%s' (%.1f%%)",
            parsed.raw_normalized[:80],
            results[0]["display"],
            results[0]["confidence"] * 100,
        )

    return results
