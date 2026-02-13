from odoo import models, fields, api, _
from ..utils.const import *


class EInvoiceLine(models.Model):
    _name = "ntp.einvoice.line"
    _description = "Einvoice Line"

    line_number = fields.Integer("No.")
    line_type = fields.Char("Type", default="1")

    einvoice_id = fields.Many2one("ntp.einvoice", "Invoice")
    currency_id = fields.Many2one(
        related="einvoice_id.currency_id",
        depends=["einvoice_id.currency_id"],
        store=True,
    )

    product_id = fields.Many2one("product.product", "Product")
    name = fields.Char("Label")
    price_unit = fields.Float(
        string="(Ref.) Price Unit",
        # related="product_id.lst_price",
        digits="Product Price",
        help="Price Taken from Invoice or default sale price in product info page",
    )
    product_code = fields.Char("Product Code")
    price_unit_without_tax = fields.Float(string="Price Unit", digits="Product Price")
    product_uom_id = fields.Many2one(
        "uom.uom",
        "(Ref.) UoM",
        related="product_id.uom_id",
    )
    product_uom = fields.Char(
        "UoM",
        help="UoM printed in EInvoice, may be depend on customer language",
    )

    quantity = fields.Float(
        "Quantity",
        default=1.0,
        digits="Product Unit of Measure",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        string="(Ref.) Taxes",
    )
    vat_percent = fields.Float("VAT (%)", related="einvoice_id.vat_percent")
    discount = fields.Float(
        string="Disc. %",
        digits="Discount",
        default=0.0,
    )
    vat_amount = fields.Monetary("Vat Amount")
    price_subtotal = fields.Monetary("Subtotal")
    price_total = fields.Monetary(
        "Total Amount", compute="_compute_price_total", store=True
    )

    # related field but store in db to searchable
    issue_date = fields.Date("Issue Date", store=True, compute="_compute_invoice_data")
    partner_id = fields.Many2one(
        "res.partner", "Customer", store=True, compute="_compute_invoice_data"
    )
    # provider einvoice status
    provider_einvoice_status = fields.Selection(
        [
            (PROVIDER_EINVOICE_STATUS_DRAFT, "Draft"),
            (PROVIDER_EINVOICE_STATUS_REQUESTED, "Requested"),
            (PROVIDER_EINVOICE_STATUS_ISSUED, "Issued"),
            (PROVIDER_EINVOICE_STATUS_REPLACE, "Replace Other"),
            (PROVIDER_EINVOICE_STATUS_BE_REPLACED, "Be Replaced"),
            (PROVIDER_EINVOICE_STATUS_ADJUST, "Adjust Other"),
            (PROVIDER_EINVOICE_STATUS_BE_ADJUSTED, "Be Adjusted"),
            (PROVIDER_EINVOICE_STATUS_CANCELED, "Canceled"),
            (PROVIDER_EINVOICE_STATUS_UNKNOWN, "Unknown"),
        ],
        "EInvoice Status",
        store=True,
        compute="_compute_invoice_data",
    )
    x_provider_mccqt = fields.Text(
        "MCCQT", help="Code that Tax Authorities Provide For Valid E-Invoice",
        compute='_compute_x_provider_mccqt',
        inverse='_inverse_x_provider_mccqt',
        search='_search_x_provider_mccqt',  # searchable on compute field
    )

    x_provider_data = fields.Text()
    x_is_product_line = fields.Boolean(compute="_compute_is_product")

    @api.depends("einvoice_id.x_provider_mccqt")
    def _compute_x_provider_mccqt(self):
        for rec in self:
            rec.x_provider_mccqt = rec.einvoice_id.x_provider_mccqt
    
    def _inverse_x_provider_mccqt(self):
        for rec in self:
            rec.einvoice_id.x_provider_mccqt = rec.x_provider_mccqt
    
    def _search_x_provider_mccqt(self, operator, value):
        return [('einvoice_id.x_provider_mccqt', operator, value)]

    @api.depends(
        "einvoice_id.issue_date",
        "einvoice_id.partner_id",
        "einvoice_id.provider_einvoice_status",
    )
    def _compute_invoice_data(self):
        for rec in self:
            rec.issue_date = rec.einvoice_id.issue_date
            rec.partner_id = rec.einvoice_id.partner_id
            rec.provider_einvoice_status = rec.einvoice_id.provider_einvoice_status

    def _compute_is_product(self):
        for rec in self:
            rec.x_is_product_line = False
            if rec.line_type == "1" or rec.product_code:
                rec.x_is_product_line = True

    def _update_price_without_tax(self):
        self.price_unit_without_tax = self.price_unit
        if self.discount:
            self.price_unit_without_tax = (
                self.price_unit_without_tax * (100 - self.discount) / 100
            )
        if len(self.tax_ids) > 0:
            for tax_id in self.tax_ids:
                if tax_id.price_include:
                    self.price_unit_without_tax = (
                        self.price_unit_without_tax / (100 + tax_id.amount) * 100
                    )

    def _update_tax_ids_n_price_unit(self):
        self.tax_ids = self.product_id.taxes_id.filtered(
            lambda tax: tax.company_id == self.einvoice_id.company_id
        )
        # re-calc price unit (no tax at all)
        if not self.price_unit:
            self.price_unit = self.product_id.lst_price
        self._update_price_without_tax()

    @api.depends("price_subtotal", "vat_amount")
    def _compute_price_total(self):
        for rec in self:
            rec.price_total = rec.price_subtotal + rec.vat_amount

    @api.onchange("product_id")
    def _update_product_info(self):
        self.product_uom_id = self.product_id.uom_id
        self.product_uom = (
            self.product_id.product_einvoice_uom or self.product_uom_id.name
        )
        self.product_code = self.product_id.default_code
        self._update_tax_ids_n_price_unit()
        self._update_product_label()

    def _update_product_label(self):
        if not self.product_id:
            return
        self.name = self.product_id.product_einvoice_label
        # if "ERROR" not in self.product_id.product_einvoice_label:
        #     self.name = self.product_id.product_einvoice_label
        # else:
        #     self.einvoice_id.message_post(
        #         body=f"Cannot update label for {self.product_id.name}, need to check legal description"
        #     )

    def _update_product_uom(self):
        # vn_text = self.env["ir.translation"].sudo().search(
        #     [
        #         ("lang", "=", "vi_VN"),
        #         ("name", "=", "uom.uom,name"),
        #         ("src", "=", self.product_uom),
        #     ]
        # )
        # self.product_uom = vn_text.value or self.product_uom
        self.product_uom = self.product_id.product_einvoice_uom or self.product_uom

    @api.onchange("quantity", "price_unit_without_tax")
    def _update_price_subtotal(self):
        if self.quantity == 0:
            self.price_subtotal = 0
        else:
            self.price_subtotal = self.price_unit_without_tax * self.quantity
        self._compute_price_total()

    @api.onchange("vat_percent", "price_subtotal")
    def _update_vat_amount(self):
        self._update_price_subtotal()
        self.vat_amount = self.price_subtotal * self.vat_percent / 100
        self._compute_price_total()

    def button_fillup_product_id(self):
        self.ensure_one()
        if self.product_id or not self.x_is_product_line:
            if not self.product_code and self.product_id:
                self.product_code = self.product_id.default_code
            return
        is_filled = False
        # 1 follow product code
        if self.product_code:
            product = self.env["product.product"].search(
                [("default_code", "=", self.product_code)]
            )
            if len(product) == 1:
                self.product_id = product.id
                is_filled = True
        # 2 follow product code
        if self.product_code and not is_filled:
            product = self.env["product.product"].search(
                [("default_code", "ilike", self.product_code)]
            )
            if len(product) == 1:
                self.product_id = product.id
                is_filled = True
        # 3 follow label printed in einvoice
        if self.name and not is_filled:
            product = self.env["product.product"].search(
                [("default_code", "=", self.name)]
            )
            if len(product) == 1:
                self.product_id = product.id
                is_filled = True
        # 4 follow label printed in einvoice
        if self.name and not is_filled:
            product = self.env["product.product"].search(
                [("default_code", "ilike", self.name)]
            )
            if len(product) == 1:
                self.product_id = product.id
                is_filled = True
        # 5 follow label printed in einvoice
        if self.name and not is_filled:
            product = (
                self.env["product.product"]
                .search([])
                .filtered(lambda x: x.default_code and x.default_code in self.name)
            )
            if len(product) == 1:
                self.product_id = product.id
                is_filled = True
        # 6 follow the pattern definition
        if not is_filled:
            active_labels = self.env["product.label.in.invoice"].search(
                [("status", "=", True)], order="priority desc"
            )
            matched_labels = active_labels.filtered(
                lambda x: x.is_match(self.product_code) or x.is_match(self.name)
            )
            if matched_labels and len(matched_labels) == 1:
                self.product_id = matched_labels.product_id
                self._update_tax_ids_n_price_unit()
        if self.product_id:
            self.product_code = self.product_id.default_code
