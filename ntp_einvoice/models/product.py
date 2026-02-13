from odoo import fields, models

class Product(models.Model):
    _inherit = "product.product"

    product_einvoice_uom = fields.Char("UoM Printed")
