# -*- coding: utf-8 -*-

import json
import logging
import os
import time

logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """Load Vietnamese administrative division data from JSON files into the database."""
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        _load_vn_address_data(env)
    except Exception as e:
        logger.error(
            "Failed to load Vietnamese address data during module install: %s",
            e, exc_info=True,
        )
        raise


def _load_vn_address_data(env):
    """Load province, district, ward data from bundled JSON files."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    start_time = time.time()

    # Check if data already loaded
    try:
        existing_count = env["vn.province"].search_count([])
        if existing_count > 0:
            logger.info("VN address data already loaded (%d provinces). Skipping.", existing_count)
            return
    except Exception as e:
        logger.error("Error checking existing VN address data: %s", e)
        raise

    logger.info("Loading Vietnamese administrative division data...")

    # --- Load provinces ---
    provinces_file = os.path.join(data_dir, "tinh_tp.json")
    try:
        with open(provinces_file, "r", encoding="utf-8") as f:
            provinces_data = json.load(f)
    except FileNotFoundError:
        logger.error("Province data file not found: %s", provinces_file)
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in province data file %s: %s", provinces_file, e)
        raise

    province_map = {}  # code -> record id
    province_vals_list = []
    skipped_provinces = 0
    for code, prov in provinces_data.items():
        try:
            province_vals_list.append({
                "code": prov["code"],
                "name": prov["name"],
                "name_with_type": prov["name_with_type"],
                "slug": prov.get("slug", ""),
                "type": prov.get("type", ""),
            })
        except KeyError as e:
            logger.warning("Province %s missing required field %s, skipping", code, e)
            skipped_provinces += 1

    try:
        provinces = env["vn.province"].create(province_vals_list)
        for prov in provinces:
            province_map[prov.code] = prov.id
        logger.info(
            "Loaded %d provinces (skipped %d).",
            len(provinces), skipped_provinces,
        )
    except Exception as e:
        logger.error("Error creating province records: %s", e, exc_info=True)
        raise

    # --- Load districts ---
    districts_file = os.path.join(data_dir, "quan_huyen.json")
    try:
        with open(districts_file, "r", encoding="utf-8") as f:
            districts_data = json.load(f)
    except FileNotFoundError:
        logger.error("District data file not found: %s", districts_file)
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in district data file %s: %s", districts_file, e)
        raise

    district_map = {}  # code -> record id
    district_vals_list = []
    skipped_districts = 0
    for code, dist in districts_data.items():
        province_id = province_map.get(dist.get("parent_code"))
        if not province_id:
            logger.warning("District %s has unknown parent_code %s", code, dist.get("parent_code"))
            skipped_districts += 1
            continue
        try:
            district_vals_list.append({
                "code": dist["code"],
                "name": dist["name"],
                "name_with_type": dist["name_with_type"],
                "slug": dist.get("slug", ""),
                "type": dist.get("type", ""),
                "province_id": province_id,
            })
        except KeyError as e:
            logger.warning("District %s missing required field %s, skipping", code, e)
            skipped_districts += 1

    # Create in batches for performance
    batch_size = 200
    districts = env["vn.district"]
    try:
        for i in range(0, len(district_vals_list), batch_size):
            batch = district_vals_list[i:i + batch_size]
            districts |= env["vn.district"].create(batch)
        for dist in districts:
            district_map[dist.code] = dist.id
        logger.info(
            "Loaded %d districts (skipped %d).",
            len(districts), skipped_districts,
        )
    except Exception as e:
        logger.error("Error creating district records at batch offset %d: %s", i, e, exc_info=True)
        raise

    # --- Load wards ---
    wards_file = os.path.join(data_dir, "xa_phuong.json")
    try:
        with open(wards_file, "r", encoding="utf-8") as f:
            wards_data = json.load(f)
    except FileNotFoundError:
        logger.error("Ward data file not found: %s", wards_file)
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in ward data file %s: %s", wards_file, e)
        raise

    ward_vals_list = []
    skipped_wards = 0
    for code, ward in wards_data.items():
        district_id = district_map.get(ward.get("parent_code"))
        if not district_id:
            logger.warning("Ward %s has unknown parent_code %s", code, ward.get("parent_code"))
            skipped_wards += 1
            continue
        try:
            ward_vals_list.append({
                "code": ward["code"],
                "name": ward["name"],
                "name_with_type": ward["name_with_type"],
                "slug": ward.get("slug", ""),
                "type": ward.get("type", ""),
                "path_with_type": ward.get("path_with_type", ""),
                "district_id": district_id,
            })
        except KeyError as e:
            logger.warning("Ward %s missing required field %s, skipping", code, e)
            skipped_wards += 1

    wards = env["vn.ward"]
    try:
        for i in range(0, len(ward_vals_list), batch_size):
            batch = ward_vals_list[i:i + batch_size]
            wards |= env["vn.ward"].create(batch)
        logger.info(
            "Loaded %d wards (skipped %d).",
            len(wards), skipped_wards,
        )
    except Exception as e:
        logger.error("Error creating ward records at batch offset %d: %s", i, e, exc_info=True)
        raise

    elapsed = time.time() - start_time
    logger.info(
        "Vietnamese administrative data loading complete! "
        "Provinces: %d, Districts: %d, Wards: %d (%.1f seconds)",
        len(provinces), len(districts), len(wards), elapsed,
    )
