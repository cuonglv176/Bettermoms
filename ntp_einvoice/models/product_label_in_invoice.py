import re
from odoo import models, fields, api, tools, _
from urllib.parse import urljoin


class ProductLabelInInvoice(models.Model):
    _name = "product.label.in.invoice"
    _description = "Product Label Matching In Invoice"

    _sql_constraints = [
        (
            "pattern_priority_uniq",
            "UNIQUE (pattern)",
            "You can not have two entries with the same pattern and priority!",
        )
    ]

    product_id = fields.Many2one("product.product")
    pattern = fields.Char("Pattern", required=True)
    priority = fields.Integer("Priority", default=1, help="Higher is prioritized")
    match_rule = fields.Selection(
        [
            ("exact_match", "Pattern Exact Match Label"),
            ("contain", "Label Is Sub String Of Pattern"),
            ("sub_string", "Pattern Is Sub String Of Label"),
            ("regex", "Pattern Is Regex Match To Label"),
        ],
        default="sub_string",
    )
    status = fields.Boolean("Enable", default=True)

    def is_match(self, label):
        if not self.pattern or not label:
            return False
        if self.match_rule == "exact_match":
            return label.lower() == self.pattern.lower()
        elif self.match_rule == "contain":
            return label.lower() in self.pattern.lower()
        elif self.match_rule == "sub_string":
            return self.pattern.lower() in label.lower()
        else:
            if re.match(self.pattern, label, re.IGNORECASE):
                return True
            return False


class Product(models.Model):
    _inherit = "product.product"

    product_label_in_invoice_ids = fields.One2many(
        "product.label.in.invoice", "product_id"
    )
    product_legal_description = fields.Char(default="")
    product_einvoice_label_rule = fields.Text(
        "Label Format Printed In EInvoice",
        default="{product_legal_description} / {name} / {default_code}",
    )
    product_einvoice_label = fields.Text(compute="_compute_product_einvoice_label")

    def get_product_einvoice_label(self):
        self.ensure_one()
        try:
            return self.product_einvoice_label_rule.format(**self.sudo().read(self._fields)[0])
        except Exception as e:
            return "ERROR"

    def _compute_product_einvoice_label(self):
        for rec in self:
            rec.product_einvoice_label = rec.get_product_einvoice_label()
