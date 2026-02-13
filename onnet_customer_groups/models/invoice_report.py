# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class AccountInvoiceReportGroupCustomer(models.Model):

    _inherit = 'account.invoice.report'

    head_code = fields.Char('Company Group Code')
    company_group_code = fields.Many2one('company.group', string='Company Group Code')

    _depends = {
        'res.partner': ['head_code'],
    }

    def _select(self):
        return super()._select() + ", contact_partner.company_group_code as company_group_code"

    def _group_by(self):
        return super()._group_by() + ", contact_partner.company_group_code"

    def _from(self):
        return super()._from() + " LEFT JOIN res_partner contact_partner ON contact_partner.id = move.partner_id"

class PurchaseOrderGroupCustomer(models.Model):

    _inherit = 'purchase.order'

    short_name = fields.Char('Partner Short Name', related='partner_id.short_name', store=True)


class saleOrderGroupCustomer(models.Model):

    _inherit = 'sale.order'

    short_name = fields.Char('Partner Short Name', related='partner_id.short_name', store=True)


class AccountMoveGroupCustomer(models.Model):

    _inherit = 'account.move'

    short_name = fields.Char('Partner Short Name', related='partner_id.short_name', store=True)

class AccountMoveLineGroupCustomer(models.Model):

    _inherit = 'account.move.line'

    company_group_code = fields.Many2one('company.group', string='Company Group Code', compute='get_company_group_code', store=True)
    short_name = fields.Char('Partner Short Name', related='partner_id.short_name', store=True)

    @api.depends('partner_id')
    def get_company_group_code(self):
        for r in self:
            r.company_group_code = self.env['company.group']
            if r.partner_id:
                r.company_group_code = r.partner_id.company_group_code