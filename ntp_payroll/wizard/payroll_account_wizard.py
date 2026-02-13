# __author__ = 'BinhTT'
from odoo import fields, models

class PayrollAccountWizard(models.Model):
    _name = 'payroll.account.wizard'

    date = fields.Date(string="Date")
    journal_id = fields.Many2one('account.journal', string="Journal")

    def create_payment_bill(self):
        ctx = self.env.context.copy()
        payslip_run_id = ctx.get('payslip_run_id')
        ctx.update({'date': self.date, 'journal_id': self.journal_id.id})
        payslip_run = self.env['hr.payslip.run'].browse([payslip_run_id]).with_context(ctx)
        payslip_run.action_create_payment_bill()
        return

