# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime


class InvoiceViettelLine(models.Model):
    _name = "invoice.viettel.line"

    currency_id = fields.Many2one(
        related='invoice_id.currency_id',
        depends=['invoice_id.currency_id'], store=True
    )
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    # price_unit = fields.Float(string="Giá")
    price_unit = fields.Float(string="Giá", digits='Product Price', compute="_compute_amount")
    actual_price_unit = fields.Float(string=_("Actual Price Unit"), digits='Product Price')
    quantity = fields.Float("Số lượng")
    name = fields.Char("Tên SP trên HĐĐT", required=True)
    invoice_line_tax_ids = fields.Many2one("account.tax", string="Thuế")
    invoice_id = fields.Many2one('invoice.viettel')
    # price_total = fields.Integer("Tiền trước thuế", compute="_sub_total")
    # price_subtotal = fields.Integer("Tổng tiền", compute="_sub_total")
    discount = fields.Float(_("Discount (%)"))
    price_total = fields.Monetary(
        "Tổng tiền",
        currency_field='currency_id')
    price_subtotal = fields.Monetary(
        "Tiền trước thuế",
        currency_field='currency_id')

    uom_id = fields.Many2one('uom.uom', string="Đơn vị")
    invoice_uom_id = fields.Char("ĐVT trên HĐĐT")
    vat_rate = fields.Integer("VAT Rate", compute="_compute_amount")
    vat_amount = fields.Monetary(
        "VAT Amount", compute="_compute_amount", currency_field='currency_id')
    is_adjustment_line = fields.Boolean(string="Thuộc hóa đơn điều chỉnh", related='invoice_id.is_adjustment_invoice')
    is_increase_adj = fields.Boolean(string="Là điều chỉnh tăng", default=False)
    account_move_line_id = fields.Many2one('account.move.line', string="Related account.move.line")

    @api.depends('quantity',
                 'invoice_line_tax_ids', 'price_total', 'price_subtotal')
    def _compute_amount(self):
        """
        Compute the amounts of the einvoice line.
        """
        for rec in self:
            if rec.quantity:
                price_unit = rec.price_subtotal / rec.quantity
            else:
                price_unit = 0
            currency = rec.currency_id or self.env.company.currency_id
            rec.price_unit = price_unit
            rec.vat_rate = int(rec.invoice_line_tax_ids.amount)
            # rec.vat_amount = currency.round(rec.price_total - rec.price_subtotal)
            # rec.vat_amount = currency.round(rec.price_subtotal*rec.vat_rate/100)
            rec.vat_amount = rec.price_subtotal*rec.vat_rate/100

    def get_vat_amount_exact(self):
        self.ensure_one()
        return self.price_subtotal*self.vat_rate/100

    def _prepare_move_line_vals(self, picking_id):
        vals = {
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom': self.uom_id.id,
            'product_uom_qty': self.quantity,
            'location_id': picking_id.location_id.id,
            'location_dest_id': picking_id.location_dest_id.id,
            'picking_id': picking_id.id,
            'date': datetime.strftime(self.invoice_id.account_move_ids.date, '%Y-%m-%d 05:%M:%S')
        }
        return vals