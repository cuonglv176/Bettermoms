# -*- coding: utf-8 -*-
"""
Migration 15.0.2.1.0 - Replace OpenAI with Google Gemini for CAPTCHA solving.

Changes:
  - Add grab_gemini_api_key column (migrate value from grab_openai_api_key)
  - Add spv_gemini_api_key column (migrate value from spv_openai_api_key)
  - Add shinhan_gemini_api_key column (migrate value from shinhan_openai_api_key)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add Gemini API key columns and migrate existing OpenAI key values."""
    if not version:
        return

    _logger.info("Migration 15.0.2.1.0: Adding Gemini API key columns...")

    # Add grab_gemini_api_key column
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS grab_gemini_api_key VARCHAR;
    """)

    # Add spv_gemini_api_key column
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS spv_gemini_api_key VARCHAR;
    """)

    # Add shinhan_gemini_api_key column
    cr.execute("""
        ALTER TABLE ntp_collector_config
        ADD COLUMN IF NOT EXISTS shinhan_gemini_api_key VARCHAR;
    """)

    _logger.info("Migration 15.0.2.1.0: Gemini API key columns added successfully.")
