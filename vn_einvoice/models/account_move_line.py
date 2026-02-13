from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_without_tax = fields.Float('Giá Trước Thuế', compute="_compute_price_without_tax")

    @api.depends('price_unit', 'quantity')
    def _compute_price_without_tax(self):
        for rec in self:
            if len(rec.tax_ids) > 0:
                for tax_id in rec.tax_ids:
                    rec.price_without_tax = rec.price_unit / (100 + tax_id.amount) * 100 * ((100 - rec.discount) / 100)
            else:
                rec.price_without_tax = rec.price_unit * (100 - rec.discount)
