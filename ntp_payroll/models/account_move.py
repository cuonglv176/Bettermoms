# __author__ = 'BinhTT'
from odoo import api, fields, models, _
from datetime import date


class PayrollAccountMove(models.Model):
    _inherit = 'account.move'

    is_payslip = fields.Boolean('Is Payslip')
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Batch Name', readonly=False,
        copy=False, ondelete='cascade',
        domain="[('company_id', '=', company_id)]")
    bill_total = fields.Float('Bill Total', compute='_compute_bill_payment_total')
    payment_total = fields.Float('Payment Total', compute='_compute_bill_payment_total')

    def _compute_bill_payment_total(self):
        for r in self:
            r.bill_total = r.payment_total = 0
            if r.is_payslip:

                    if r.journal_id.type in ('general', 'purchase'):
                        r.bill_total = abs(r.amount_total) * (-1 if r.journal_id.type != 'general' else 1)
                    if r.journal_id.type in ('general', 'bank', 'cash'):
                        r.payment_total = abs(r.amount_total) * (-1 if r.journal_id.type != 'general' else 1)

    # def action_post(self):
    #     res = super(PayrollAccountMove, self).action_post()
    #     if self.is_payslip:
    #         partner_ids = self.line_ids.filtered(lambda x: x.credit > 0).partner_id
    #         for r in partner_ids:
    #             invoice_line_ids = []
    #             line_ids = self.line_ids.filtered(lambda x: x.partner_id == r and x.credit > 0)
    #             data = self._prepare_bill_data(r)
    #             for line in line_ids:
    #                 invoice_line_ids.append((0, 0, {
    #                     'name': line.name,
    #                     'account_id': line.account_id.id,
    #                     'price_unit': line.credit,
    #                     'quantity': 1,
    #                 }))
    #             data.update({'invoice_line_ids': invoice_line_ids})
    #             msg_body = _(
    #                 "Invoice created from <a href=# data-oe-model=account.move "
    #                 "data-oe-id=%d>%s</a>."
    #             ) % (self.id, self.name)
    #             created = self.env['account.move'].sudo().create(data)
    #             created.message_post(body=msg_body)
    #     return res

    def _prepare_bill_data(self, partner):
        data = {
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': date.today(),
            'payslip_run_id': self.payslip_run_id.id,
            'is_payslip': True,
            # 'invoice_line_ids': [(0, 0, {
            #     'name': partner.name,
            #     'account_id': partner.account_id.id,
            #     'price_unit': partner.credit,
            #     'quantity': 1,
            # })],
        }
        return data