# -*- coding: utf-8 -*-
"""
AI-Powered Address Suggestion Engine
=====================================
Uses OpenAI-compatible API to parse and suggest Vietnamese addresses
when the fuzzy matching engine cannot find a confident match.

Falls back gracefully if the API is unavailable or not configured.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# Default prompt template for address parsing
_SYSTEM_PROMPT = """Bạn là một hệ thống phân tích địa chỉ Việt Nam. Nhiệm vụ của bạn là phân tích chuỗi địa chỉ đầu vào và trích xuất:
- province: Tỉnh/Thành phố (ví dụ: "Hà Nội", "Hồ Chí Minh", "Đà Nẵng")
- district: Quận/Huyện (ví dụ: "Quận 1", "Huyện Bình Chánh")
- ward: Phường/Xã (ví dụ: "Phường Bến Nghé", "Xã Vĩnh Lộc A")
- street: Số nhà và tên đường

Trả về JSON với format:
{"province": "...", "district": "...", "ward": "...", "street": "...", "confidence": 0.0-1.0}

Nếu không xác định được thành phần nào, để giá trị rỗng "".
confidence là mức độ tin cậy từ 0.0 đến 1.0.
CHỈ trả về JSON, không thêm text nào khác."""


def ai_suggest_address(raw_address, env, model="gpt-4.1-nano"):
    """Use AI to parse and suggest address components from raw text.

    Args:
        raw_address (str): The raw address string to parse.
        env: Odoo environment (used to read config parameters).
        model (str): The AI model to use.

    Returns:
        dict or None: Parsed address components, or None if AI is unavailable.
            Keys: province, district, ward, street, confidence
    """
    if not raw_address or not raw_address.strip():
        return None

    # Check if AI address suggestion is enabled
    try:
        enabled = env["ir.config_parameter"].sudo().get_param(
            "ntp_address_lookup.ai_suggest_enabled", default="False"
        ) == "True"
        if not enabled:
            logger.debug("AI address suggestion is disabled in settings")
            return None
    except Exception as e:
        logger.warning("Could not read AI suggestion config: %s", e)
        return None

    # Get API key from system parameters or environment
    try:
        api_key = env["ir.config_parameter"].sudo().get_param(
            "ntp_address_lookup.openai_api_key", default=""
        )
        api_base_url = env["ir.config_parameter"].sudo().get_param(
            "ntp_address_lookup.openai_base_url", default=""
        )
    except Exception as e:
        logger.warning("Could not read AI API config: %s", e)
        return None

    if not api_key:
        # Try environment variable as fallback
        import os
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.debug("No OpenAI API key configured for address suggestion")
            return None

    try:
        import openai
    except ImportError:
        logger.warning(
            "openai package not installed. Install with: pip install openai"
        )
        return None

    try:
        client_kwargs = {"api_key": api_key}
        if api_base_url:
            client_kwargs["base_url"] = api_base_url

        client = openai.OpenAI(**client_kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": raw_address.strip()},
            ],
            temperature=0.1,
            max_tokens=300,
            timeout=10,
        )

        content = response.choices[0].message.content.strip()
        logger.debug("AI address suggestion raw response: %s", content)

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(content)

        # Validate result structure
        required_keys = ["province", "district", "ward"]
        for key in required_keys:
            if key not in result:
                result[key] = ""

        if "street" not in result:
            result["street"] = ""
        if "confidence" not in result:
            result["confidence"] = 0.5

        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

        logger.info(
            "AI address suggestion for '%s': province='%s', district='%s', "
            "ward='%s' (confidence=%.0f%%)",
            raw_address[:80],
            result.get("province", ""),
            result.get("district", ""),
            result.get("ward", ""),
            result["confidence"] * 100,
        )

        return result

    except json.JSONDecodeError as e:
        logger.warning(
            "AI address suggestion returned invalid JSON for '%s': %s",
            raw_address[:80], e,
        )
        return None
    except openai.APIError as e:
        logger.error(
            "OpenAI API error during address suggestion: %s", e,
        )
        return None
    except openai.APIConnectionError as e:
        logger.warning(
            "Could not connect to OpenAI API for address suggestion: %s", e,
        )
        return None
    except openai.RateLimitError as e:
        logger.warning(
            "OpenAI API rate limit reached during address suggestion: %s", e,
        )
        return None
    except Exception as e:
        logger.error(
            "Unexpected error in AI address suggestion for '%s': %s",
            raw_address[:80], e, exc_info=True,
        )
        return None


def ai_match_to_db(ai_result, env):
    """Match AI-parsed address components to database records.

    Args:
        ai_result (dict): Result from ai_suggest_address().
        env: Odoo environment.

    Returns:
        list[dict]: Matched results in the same format as auto_detect_address().
    """
    if not ai_result:
        return []

    results = []
    province_name = (ai_result.get("province") or "").strip()
    district_name = (ai_result.get("district") or "").strip()
    ward_name = (ai_result.get("ward") or "").strip()

    if not province_name:
        return []

    try:
        # Search province
        provinces = env["vn.province"].sudo().search([
            "|", "|",
            ("name", "ilike", province_name),
            ("name_with_type", "ilike", province_name),
            ("slug", "ilike", province_name.lower().replace(" ", "-")),
        ], limit=3)

        if not provinces:
            logger.debug("AI match: no province found for '%s'", province_name)
            return []

        for prov in provinces:
            # Search district within province
            district_domain = [("province_id", "=", prov.id)]
            if district_name:
                district_domain += [
                    "|",
                    ("name", "ilike", district_name),
                    ("name_with_type", "ilike", district_name),
                ]
            districts = env["vn.district"].sudo().search(
                district_domain, limit=3,
            )

            if not districts and district_name:
                # Province-only result
                results.append({
                    "province_id": prov.id,
                    "district_id": False,
                    "ward_id": False,
                    "province_name": prov.name_with_type or prov.name,
                    "district_name": "",
                    "ward_name": "",
                    "confidence": round(ai_result["confidence"] * 0.5, 4),
                    "display": prov.name_with_type or prov.name,
                    "source": "ai",
                })
                continue

            for dist in districts:
                # Search ward within district
                ward_domain = [("district_id", "=", dist.id)]
                if ward_name:
                    ward_domain += [
                        "|",
                        ("name", "ilike", ward_name),
                        ("name_with_type", "ilike", ward_name),
                    ]
                wards = env["vn.ward"].sudo().search(
                    ward_domain, limit=3,
                )

                if wards:
                    for ward in wards:
                        confidence = ai_result["confidence"]
                        if ward_name and district_name:
                            confidence *= 0.95  # High match
                        elif district_name:
                            confidence *= 0.80
                        else:
                            confidence *= 0.60

                        results.append({
                            "province_id": prov.id,
                            "district_id": dist.id,
                            "ward_id": ward.id,
                            "province_name": prov.name_with_type or prov.name,
                            "district_name": dist.name_with_type or dist.name,
                            "ward_name": ward.name_with_type or ward.name,
                            "confidence": round(confidence, 4),
                            "display": ward.path_with_type or "%s, %s, %s" % (
                                ward.name_with_type or ward.name,
                                dist.name_with_type or dist.name,
                                prov.name_with_type or prov.name,
                            ),
                            "source": "ai",
                        })
                else:
                    # District-only result
                    confidence = ai_result["confidence"] * 0.65
                    results.append({
                        "province_id": prov.id,
                        "district_id": dist.id,
                        "ward_id": False,
                        "province_name": prov.name_with_type or prov.name,
                        "district_name": dist.name_with_type or dist.name,
                        "ward_name": "",
                        "confidence": round(confidence, 4),
                        "display": "%s, %s" % (
                            dist.name_with_type or dist.name,
                            prov.name_with_type or prov.name,
                        ),
                        "source": "ai",
                    })

    except Exception as e:
        logger.error(
            "Error matching AI result to database: %s", e, exc_info=True,
        )
        return []

    # Sort by confidence descending
    results.sort(key=lambda r: -r["confidence"])
    return results[:5]
