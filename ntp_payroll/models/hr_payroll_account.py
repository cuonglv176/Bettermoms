#-*- coding:utf-8 -*-

from collections import defaultdict
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, plaintext2html
from datetime import date
from collections import defaultdict
class NTPHrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        """
            Generate the accounting entries related to the selected payslips
            A move is created for each journal and for each month.
        """
        res = super(NTPHrPayslip, self).action_payslip_done()
        if self.move_id:
            self.move_id.is_payslip = True
            if self.payslip_run_id:
                self.move_id.ref = self.payslip_run_id.name
                self.move_id.payslip_run_id = self.payslip_run_id
        return res

    def _get_existing_lines(self, line_ids, line, account_id, debit, credit):
        super(NTPHrPayslip, self)._get_existing_lines(line_ids, line, account_id, debit, credit)
        return False

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        res = super(NTPHrPayslip, self)._prepare_line_values(line, account_id, date, debit, credit)
        res.update({'name': line.name + ' - ' + line.employee_id.name})
        return res

class NTPHrPaysliprun(models.Model):
    _inherit = 'hr.payslip.run'

    move_ids = fields.One2many('account.move', 'payslip_run_id', readonly=1)
    payment_ids = fields.One2many(comodel_name='account.payment', inverse_name='payslip_run_id', readonly=1)
    payment_count = fields.Integer(compute='_count_payment')

    def _count_payment(self):
        for payslip_run in self:
            payslip_run.payment_count = len(payslip_run.payment_ids)

    def action_open_create_payment_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': 'Create Payment Employee',
            'view_mode': 'form',
            'res_model': 'payroll.account.wizard',
            'context': {'payslip_run_id': self.id},
        }

    def action_create_vendor_payment(self):
        payslip_ids = self.slip_ids
        third_partner = defaultdict(list)

        for payslip in payslip_ids:
            msg_body = _(
                "Invoice created from <a href=# data-oe-model=hr.payslip.run "
                "data-oe-id=%d>Payslip Batch %s</a>."
            ) % (self.id, self.name)
            data = self._prepare_bill_data(payslip)
            data.update(amount=payslip.net_wage)
            created = self.env['account.payment'].sudo().create(data)
            created.message_post(body=msg_body)
            for partner in payslip.move_id.line_ids.partner_id:
                third_partner[partner] = 0
                for invoice_line in payslip.move_id.line_ids.filtered(
                        lambda x: x.partner_id == partner and x.credit > 0):
                    third_partner[partner] += invoice_line.credit
        for partner, total in third_partner.items():
            memo = self.name
            partner_id = partner.id
            ctx = self.env.context
            data = {
                'partner_type': 'supplier',
                'payment_type': "outbound",
                'partner_id': partner_id,
                'date': self.date_end,
                # 'payslip_run_id': self.payslip_run_id.id,
                'is_payslip': True,
                'amount': total,
                'ref': memo,
                'payslip_run_id': self.id,
                'journal_id': ctx.get('journal_id') or 64,
            }
            created = self.env['account.payment'].sudo().create(data)



    def action_create_vendor_bill(self):
        payslip_ids = self.slip_ids
        third_partner = defaultdict(list)
        for payslip in payslip_ids:
            msg_body = _(
                "Invoice created from <a href=# data-oe-model=hr.payslip.run "
                "data-oe-id=%d>Payslip Batch %s</a>."
            ) % (self.id, self.name)
            data = self._prepare_vendor_bill_data(payslip)
            created = self.env['account.move'].sudo().create(data)
            created.message_post(body=msg_body)

            for partner in payslip.move_id.line_ids.partner_id:
                third_partner[partner] = []
                for invoice_line in payslip.move_id.line_ids.filtered(lambda x:x.partner_id == partner and x.credit > 0):
                    third_partner[partner] += invoice_line
            # invoice = self.env['account.move'].with_context(asset_type='purchase').create(self._prepare_bill_data(payslip))
        for partner, invoice_line in third_partner.items():
            memo = self.name
            partner_id = partner.id
            ctx = self.env.context
            msg_body = _(
                "Invoice created from <a href=# data-oe-model=hr.payslip.run "
                "data-oe-id=%d>Payslip Batch %s</a>."
            ) % (self.id, self.name)
            data = {
                'move_type': 'in_invoice',
                'partner_id': partner_id,
                'invoice_date': self.date_end,
                'journal_id': ctx.get('journal_id') or self.env['account.journal'].search([('type', '=', 'purchase')])[
                    0].id,
                'date': self.date_end,
                'ref': memo,
                'payslip_run_id': self.id,
                'is_payslip': True,
                'invoice_line_ids': [
                    (0, 0, {
                        'name': line.name,
                        'price_unit': line.credit,
                        'quantity': 1.0,
                        'account_id': line.account_id.id,
                    }) for line in invoice_line
                ],
            }
            created = self.env['account.move'].sudo().create(data)
            created.message_post(body=msg_body)
        return

    def action_create_payment_bill(self):
        payslip_ids = self.slip_ids.filtered(lambda x: x.state == 'done')
        for payslip in payslip_ids:
            msg_body = _(
                "Invoice created from <a href=# data-oe-model=hr.payslip.run "
                "data-oe-id=%d>Payslip Batch %s</a>."
            ) % (self.id, self.name)
            data = self._prepare_bill_data(payslip)
            created = self.env['account.payment'].sudo().create(data)
            created.message_post(body=msg_body)

        # for payslip in self.slip_ids:
            # invoice = self.env['account.move'].with_context(asset_type='purchase').create(self._prepare_bill_data(payslip))
        return

    def _prepare_vendor_bill_data(self, payslip):
        memo = payslip.payslip_run_id.name + ' - ' + payslip.employee_id.name
        partner_id = payslip.employee_id.with_context(active_test=False).partner_id.id or payslip.employee_id.address_home_id.id
        ctx = self.env.context
        data = {
            'move_type': 'in_invoice',
            'partner_id': partner_id,
            'invoice_date': payslip.date,
            'journal_id': ctx.get('journal_id') or self.env['account.journal'].search([('type', '=', 'purchase')])[0].id,
            'date': payslip.date,
            'ref': memo,
            'payslip_run_id': self.id,
            'is_payslip': True,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Vendor Payment %d ₫ - %s - Employee - %s' %(payslip.net_wage, payslip.employee_id.name, payslip.date.strftime('%d-%m-%Y')),
                    'price_unit': payslip.net_wage,
                    'quantity': 1.0,
                    'account_id': self.env.company.account_journal_payment_credit_account_id.id,
                }),
            ],
        }

        return data

    def _prepare_bill_data(self, payslip):
        memo = payslip.payslip_run_id.name + ' - ' + payslip.employee_id.name
        partner_id = payslip.employee_id.with_context(active_test=False).partner_id.id or payslip.employee_id.address_home_id.id
        ctx = self.env.context
        data = {
            'partner_type': 'supplier',
            'payment_type': "outbound",
            'partner_id': partner_id,
            'date': ctx.get('date', payslip.date),
            # 'payslip_run_id': self.payslip_run_id.id,
            'is_payslip': True,
            # 'amount': payslip.net_wage,
            'ref': memo,
            'payslip_run_id': self.id,
            'journal_id': ctx.get('journal_id') or 64,
        }
        return data

    def action_open_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [['payslip_run_id', 'in', self.ids], ['is_payslip', '=', True]],
            "name": "Payments",
        }
