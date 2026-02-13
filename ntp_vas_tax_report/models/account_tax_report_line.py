# __author__ = 'BinhTT'
from odoo import models, fields
class AccountTaxReportLine(models.Model):
    _inherit = "account.tax.report.line"

    vas_tax_field = fields.Char('VAS Tax Declaration Field')
    vas_tax_type = fields.Selection([('vat_amount', 'VAT Amount'),
                                     ('untax_amount', 'Untax Amount')], string='VAS Tax Type')


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    tax_group = fields.Many2one('account.tax.group', 'Tax Group')