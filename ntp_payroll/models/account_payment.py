# __author__ = 'BinhTT'
from odoo import  models, fields

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_payslip = fields.Boolean("Is Payslip")
    payslip_run_id = fields.Many2one(comodel_name="hr.payslip.run")
