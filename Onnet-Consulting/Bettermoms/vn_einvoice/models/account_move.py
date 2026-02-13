# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _

from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    vsi_status = fields.Selection([
        ('draft', 'Chưa tạo HĐĐT'),
        ('created', 'Đã tạo HĐĐT'),
        ('canceled', 'Đã hủy HĐĐT'),
    ],
        string='Trạng thái HĐĐT',
        default='draft', copy=False)
    invoice_viettel_ids = fields.Many2many('invoice.viettel',
                                           string='Hóa đơn điện tử', copy=False)
    paymentType = fields.Selection(
        [('ck', 'Bank transfer'),
         ('tm', 'Cash'),
         ('tm/ck', 'Bank transfer / Cash')],
        string="Payment Type")
    invoiceStatus = fields.Selection(
        [('0', _(u'Không lấy hóa đơn')),
         ('1', _(u'Lấy hóa đơn ngay')),
         ('2', _(u'Lấy hóa đơn sau'))],
        string="Invoice Status")
    company_branch_id = fields.Many2one(
        "company.branch", string="Company Branch",
        store=True)
    buyerName = fields.Char('Người mua hàng')

    vsi_template = fields.Char(string="Mẫu Hóa Đơn")
    vsi_series = fields.Char(string="Ký hiệu hóa đơn")
    vsi_number = fields.Char(string="Số hóa đơn")
    invoice_address = fields.Char('Địa chỉ xuất hóa đơn',
                                  related="partner_id.street")
    buyer_vat = fields.Char("MST", related="partner_id.vat")
    company_branch_vat = fields.Many2one("company.branch", string="Company Branch Vat")
    einvoice_date = fields.Date("Ngày hoá đơn điện tử", compute='_compute_einvoice_date', store=True)
    invoice_viettel_count = fields.Integer(compute='_compute_invoice_viettel_count')

    @api.depends('invoice_viettel_ids')
    def _compute_invoice_viettel_count(self):
        for r in self:
            r.invoice_viettel_count = len(r.invoice_viettel_ids)

    @api.depends('invoice_viettel_ids.date_invoice', 'invoice_viettel_ids.vsi_status')
    def _compute_einvoice_date(self):
        for move in self:
            einvoice_date = False
            if move.vsi_number:
                einvoices = self.env['invoice.viettel'].sudo().search([('name', '=', move.vsi_number), ('company_id.id', '=', move.company_id.id)])
                for einvoice in einvoices:
                    if einvoice.vsi_status == 'created':
                        einvoice_date = einvoice.date_invoice
                        break
                if not einvoice_date:
                    einvoice_date = move.date
            move.einvoice_date = einvoice_date

    def create_vninvoice(self):
        if len(self.invoice_viettel_ids) > 0:
            raise UserError("Đã tạo Hóa Đơn Điện Tử")

        list_tax = []
        list_data = []
        for item in self.invoice_line_ids:
            if item.tax_ids.id not in list_tax:
                list_tax.append(item.tax_ids.id)
                list_data.append({
                    'id_tax': item.tax_ids.id,
                    'invoice_line_id': [item.id]
                })
            if item.tax_ids.id in list_tax:
                for val in list_data:
                    if val['id_tax'] == item.tax_ids.id and \
                            item.id not in val['invoice_line_id']:
                        val['invoice_line_id'].append(item.id)

        list_invoice_create = []
        for invoice in list_data:
            currency = self.currency_id
            invoice_line = []
            for line in invoice['invoice_line_id']:
                invoice_line_id = self.env['account.move.line'].browse(line)
                if invoice_line_id.quantity > 0:
                    data_line = {
                        'product_id': invoice_line_id.product_id.id,
                        'price_subtotal': currency.round(invoice_line_id.price_subtotal),
                        'price_total': currency.round(invoice_line_id.price_total),
                        'quantity': invoice_line_id.quantity,
                        'name': invoice_line_id.name,
                        'invoice_line_tax_ids': invoice_line_id.tax_ids.id,
                        'uom_id': invoice_line_id.product_uom_id.id,
                        'account_move_line_id': invoice_line_id.id
                    }
                invoice_line.append([0, 0, data_line])
        invoice_data = {
            'partner_id': self.partner_id.id,
            'date_invoice': fields.Datetime.today(),
            'company_id': self.company_id.id,
            'company_branch_id': self.company_branch_id.id,
            'invoiceStatus': self.invoiceStatus,
            'buyerName': self.buyerName,
            'user_id': self.user_id.id,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'paymentType': self.paymentType,
            'invoice_line_ids': invoice_line,
            'amount_untaxed': round(self.amount_untaxed),
            'amount_tax': int(self.amount_tax),
            'amount_total': int(self.amount_total),
            'fkey': str(int(datetime.utcnow().timestamp())) + str(self.company_branch_id.id) + str(self.id)
        }

        invoice_viettel_id = self.env['invoice.viettel'].create(invoice_data)
        list_invoice_create.append(invoice_viettel_id.id)
        self.write({'invoice_viettel_ids': [[6, False, list_invoice_create]]})
        return {
            "type": "ir.actions.act_window",
            "res_model": "invoice.viettel",
            "views": [[False, "form"]],
            "res_id": invoice_viettel_id.id,
            "target": "new",
        }

    # cấm xóa
    def unlinkForApiUser(self):
        if self.env.user.id == 728:     # api@nhanlucsieuviet.com
            return super(AccountMove, self.with_context(force_delete=True)).unlink()
        else:
            return super(AccountMove, self).unlink()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    company_branch_id = fields.Many2one("company.branch", string="Company Branch", compute='_compute_company_branch')
    einvoice_number = fields.Char(string="E-Invoice Number", compute='_compute_einvoice_number', store=True )
    einvoice_date = fields.Date(string="E-Invoice Date", compute='_compute_einvoice_number', store=True)

    @api.depends('move_id.invoice_viettel_ids')
    def _compute_einvoice_number(self):
        for line in self:
            einvoice_number = ''
            einvoice_date = False
            if line.move_id and line.move_id.invoice_viettel_ids:
                for e_invoice in line.move_id.invoice_viettel_ids:
                    if e_invoice.vsi_status == 'created':
                        einvoice_number = e_invoice.name
                        einvoice_date = e_invoice.date_invoice
            line.einvoice_number = einvoice_number
            line.einvoice_date = einvoice_date

    @api.depends('move_id.company_branch_id', 'move_id.company_branch_vat')
    def _compute_company_branch(self):
        for line in self:
            company_branch_id = False
            if line.move_id:
                if line.move_id.company_branch_vat:
                    company_branch_id = line.move_id.company_branch_vat.id
                elif line.move_id.company_branch_id:
                    company_branch_id = line.move_id.company_branch_id.id

            line.company_branch_id = company_branch_id

    def task_recompute_tax_base_amount(self, move_line_id):
        aml = self.env['account.move.line'].sudo().search([('id', '=', move_line_id)])
        aml.move_id._recompute_dynamic_lines(recompute_all_taxes=False, recompute_tax_base_amount=True)
        # for move_line in aml:
        #     base_lines = move_line.move_id.line_ids.filtered(
        #         lambda line: move_line.tax_line_id in line.tax_ids and move_line.product_id == line.product_id)
        #     move_line.tax_base_amount = abs(sum(base_lines.mapped('balance')))