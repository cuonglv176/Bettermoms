# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
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

    _sql_constraints = [
        (
            "shopee_order_id_uniq",
            "UNIQUE(x_shopee_order_id)",
            "This Shopee Order ID already exists! "
            "Each Shopee order can only be linked once.",
        ),
    ]

    @api.constrains("x_order_source", "x_shopee_order_id")
    def _check_shopee_order_id(self):
        """Ensure Shopee Order ID is provided when source is Shopee."""
        for order in self:
            if order.x_order_source == "shopee" and not order.x_shopee_order_id:
                raise ValidationError(
                    "Shopee Order ID is required when Order Source is 'Shopee'. "
                    "Please provide the marketplace reference code."
                )

    def action_confirm(self):
        """Override to block confirmation of Shopee orders without ID."""
        for order in self:
            if order.x_order_source == "shopee" and not order.x_shopee_order_id:
                raise UserError(
                    "Cannot confirm this order: Shopee Order ID is mandatory "
                    "for orders with Source = 'Shopee'. "
                    "Please enter the Shopee reference code before confirming."
                )
        return super().action_confirm()
