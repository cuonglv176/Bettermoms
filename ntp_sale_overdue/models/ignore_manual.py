# __author__ = 'BinhTT'
from odoo import models, fields

class IgnoreManual(models.Model):
    _name = 'ignore.manual'
    ignore_reason = fields.Char('Reason')
    _rec_name = 'ignore_reason'

class IgnoreManualWizard(models.TransientModel):
    _name = 'ignore.manual.wizard'
    ignore_manual = fields.Many2one('ignore.manual')

    def confirm(self):
        if self.env.context.get('active_id'):
            sale_obj = self.env['sale.order'].browse(self.env.context.get('active_id'))
            sale_obj.write({'ignore_order': True, 'ignore_manual_reason': self.ignore_manual})
            note = 'Your order has been Ignore. Reason: %s' %(self.ignore_manual.ignore_reason)
            sale_obj.activity_schedule(act_type_xmlid='mail.mail_activity_data_todo', note=note)
        return