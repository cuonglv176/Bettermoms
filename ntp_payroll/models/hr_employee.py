# __author__ = 'BinhTT'

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, plaintext2html
from datetime import date

class NTPHrEmployee(models.Model):
    _inherit = 'hr.employee'

    partner_id = fields.Many2one('res.partner')
    payment_count = fields.Integer(compute="_count_payment")

    def _count_payment(self):
        for r in self:
            if r.partner_id:
                payments = self.env['account.payment'].search([('partner_id', '=', r.partner_id.id), ('is_payslip', '=', True)])
                r.payment_count = len(payments)
            else:
                r.payment_count = 0

    def action_open_payments(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [['partner_id', 'in', self.partner_id.ids], ['is_payslip', '=', True]],
            "name": "Payments",
        }