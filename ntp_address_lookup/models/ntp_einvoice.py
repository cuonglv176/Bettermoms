# -*- coding: utf-8 -*-

import logging

from odoo import models

logger = logging.getLogger(__name__)


class NtpEinvoice(models.Model):
    _inherit = "ntp.einvoice"

    def _build_full_address(self, partner):
        """Build a full address string including ward and district.

        Format: "street, ward, district, city/province"
        This matches the format expected by Viettel's buyerAddressLine field.
        """
        try:
            parts = [
                partner.street or "",
                partner.x_ward_id.name_with_type if partner.x_ward_id else "",
                partner.x_district_id.name_with_type if partner.x_district_id else "",
                partner.x_province_id.name_with_type if partner.x_province_id else (partner.city or ""),
            ]
            address = ", ".join([p for p in parts if p.strip()])
            logger.debug(
                "Built full address for partner [%s] %s: %s",
                partner.id, partner.name, address,
            )
            return address
        except Exception as e:
            logger.error(
                "Error building full address for partner [%s]: %s",
                partner.id if partner else "N/A", e, exc_info=True,
            )
            return partner.street or ""

    def button_update_buyer_info(self):
        """Override to include ward/district in buyer_address."""
        try:
            super().button_update_buyer_info()
        except Exception as e:
            logger.error(
                "Error in parent button_update_buyer_info for einvoice [%s]: %s",
                self.id, e, exc_info=True,
            )
            raise

        # After parent sets buyer_address from partner.street only,
        # replace it with the full address including ward/district
        if not self.partner_id or self.buyer_type == "unidentified":
            return

        try:
            # Determine which partner record provides the address
            partner = self.partner_id
            if self.buyer_type == "company" and self.partner_id.child_ids:
                for child in self.partner_id.child_ids:
                    if child.type == "invoice" and child.street:
                        partner = child
                        break
            if self.invoice_address:
                partner = self.invoice_address

            full_address = self._build_full_address(partner)
            if full_address:
                self.buyer_address = full_address
                logger.info(
                    "Updated buyer_address for einvoice [%s] with full VN address",
                    self.id,
                )
        except Exception as e:
            logger.error(
                "Error updating buyer address for einvoice [%s]: %s",
                self.id, e, exc_info=True,
            )
