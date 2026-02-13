# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_order_source = fields.Selection(
        [
            ("direct", "Direct Sale"),
            ("shopee", "Shopee"),
            ("grab", "Grab"),
        ],
        string="Order Source",
        default="direct",
        tracking=True,
        help="Indicates where this order originated from.",
    )
    x_shopee_order_id = fields.Char(
        "Shopee Order ID",
        index=True,
        tracking=True,
        copy=False,
        help="The unique marketplace order reference from Shopee.",
    )
    x_grab_order_id = fields.Char(
        "Grab Order ID",
        index=True,
        tracking=True,
        copy=False,
        help="The unique marketplace order reference from Grab.",
    )

    _sql_constraints = [
        (
            "shopee_order_id_uniq",
            "UNIQUE(x_shopee_order_id)",
            "This Shopee Order ID already exists! "
            "Each Shopee order can only be linked once.",
        ),
        (
            "grab_order_id_uniq",
            "UNIQUE(x_grab_order_id)",
            "This Grab Order ID already exists! "
            "Each Grab order can only be linked once.",
        ),
    ]

    @api.constrains("x_order_source", "x_shopee_order_id")
    def _check_shopee_order_id(self):
        """Ensure Shopee Order ID is provided when source is Shopee."""
        for order in self:
            if order.x_order_source == "shopee" and not order.x_shopee_order_id:
                _logger.warning(
                    "Shopee Order ID missing for SO [%s] %s",
                    order.id, order.name,
                )
                raise ValidationError(_(
                    "Shopee Order ID is required when Order Source is 'Shopee'. "
                    "Please provide the marketplace reference code."
                ))

    @api.constrains("x_order_source", "x_grab_order_id")
    def _check_grab_order_id(self):
        """Ensure Grab Order ID is provided when source is Grab."""
        for order in self:
            if order.x_order_source == "grab" and not order.x_grab_order_id:
                _logger.warning(
                    "Grab Order ID missing for SO [%s] %s",
                    order.id, order.name,
                )
                raise ValidationError(_(
                    "Grab Order ID is required when Order Source is 'Grab'. "
                    "Please provide the marketplace reference code."
                ))

    def action_confirm(self):
        """Override to block confirmation of marketplace orders without IDs."""
        for order in self:
            if order.x_order_source == "shopee" and not order.x_shopee_order_id:
                _logger.warning(
                    "Attempted to confirm Shopee SO [%s] %s without Order ID",
                    order.id, order.name,
                )
                raise UserError(_(
                    "Cannot confirm this order: Shopee Order ID is mandatory "
                    "for orders with Source = 'Shopee'. "
                    "Please enter the Shopee reference code before confirming."
                ))
            if order.x_order_source == "grab" and not order.x_grab_order_id:
                _logger.warning(
                    "Attempted to confirm Grab SO [%s] %s without Order ID",
                    order.id, order.name,
                )
                raise UserError(_(
                    "Cannot confirm this order: Grab Order ID is mandatory "
                    "for orders with Source = 'Grab'. "
                    "Please enter the Grab reference code before confirming."
                ))

        try:
            result = super().action_confirm()
            for order in self:
                if order.x_order_source != "direct":
                    _logger.info(
                        "Confirmed %s order [%s] %s (marketplace_id=%s)",
                        order.x_order_source,
                        order.id,
                        order.name,
                        order.x_shopee_order_id or order.x_grab_order_id or "",
                    )
            return result
        except (UserError, ValidationError):
            raise
        except Exception as e:
            _logger.error(
                "Error confirming sale order(s) %s: %s",
                self.mapped("name"), e, exc_info=True,
            )
            raise UserError(
                _("Error confirming order: %s") % str(e)
            ) from e

    @api.onchange("x_order_source")
    def _onchange_order_source(self):
        """Clear marketplace IDs when source changes."""
        if self.x_order_source != "shopee":
            self.x_shopee_order_id = False
        if self.x_order_source != "grab":
            self.x_grab_order_id = False
