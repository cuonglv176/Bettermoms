# -*- coding: utf-8 -*-
"""
Migration 15.0.2.1.0 - Replace AI solutions with 2captcha.com for CAPTCHA solving.

Changes:
  - Add grab_captcha_api_key column (primary 2captcha key)
  - Add spv_captcha_api_key column (primary 2captcha key)
  - Add shinhan_captcha_api_key column (primary 2captcha key)
  - Add grab_gemini_api_key column (kept for backward compatibility)
  - Add spv_gemini_api_key column (kept for backward compatibility)
  - Add shinhan_gemini_api_key column (kept for backward compatibility)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add 2captcha API key columns and legacy Gemini/OpenAI key columns."""
    if not version:
        return

    _logger.info("Migration 15.0.2.1.0: Adding 2captcha API key columns...")

    # Add primary 2captcha API key columns
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS grab_captcha_api_key VARCHAR;
    """)
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS spv_captcha_api_key VARCHAR;
    """)
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS shinhan_captcha_api_key VARCHAR;
    """)

    # Add legacy Gemini columns (kept for backward compatibility)
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS grab_gemini_api_key VARCHAR;
    """)
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS spv_gemini_api_key VARCHAR;
    """)
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS shinhan_gemini_api_key VARCHAR;
    """)

    _logger.info("Migration 15.0.2.1.0: All CAPTCHA API key columns added successfully.")
