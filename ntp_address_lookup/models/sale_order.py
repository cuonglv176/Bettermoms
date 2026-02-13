# -*- coding: utf-8 -*-

import logging

from odoo import models, _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def button_verify_shipping_address(self):
        """Open address lookup wizard for the shipping address partner."""
        self.ensure_one()
        if not self.partner_shipping_id:
            logger.warning(
                "Cannot open address lookup for SO [%s]: no shipping partner set",
                self.name,
            )
            raise UserError(_("Please set a shipping address before verifying."))

        logger.info(
            "Opening address lookup for shipping partner of SO [%s]",
            self.name,
        )
        try:
            return self.partner_shipping_id.button_verify_address()
        except UserError:
            raise
        except Exception as e:
            logger.error(
                "Error opening address lookup for SO [%s] shipping partner [%s]: %s",
                self.name, self.partner_shipping_id.id, e, exc_info=True,
            )
            raise UserError(
                _("Could not open address lookup: %s") % str(e)
            ) from e
