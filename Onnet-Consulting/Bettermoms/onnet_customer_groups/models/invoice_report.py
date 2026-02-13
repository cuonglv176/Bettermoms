# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class AccountInvoiceReportGroupCustomer(models.Model):

    _inherit = 'account.invoice.report'

    head_code = fields.Char('Company Group Code')

    _depends = {
        'res.partner': ['head_code'],
    }

    def _select(self):
        return super()._select() + ", contact_partner.head_code as head_code"

    def _group_by(self):
        return super()._group_by() + ", contact_partner.head_code"

    def _from(self):
        return super()._from() + " LEFT JOIN res_partner contact_partner ON contact_partner.id = move.partner_id"
