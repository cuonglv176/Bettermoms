# __author__ = 'BinhTT'


from odoo import api, fields, models
from threading import Thread

class SaleOverDueConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    date_overdue_config = fields.Selection([
        ('effective_date', 'Effective Date'),
        ('scheduled_date', 'Scheduled Date'),
        ('commitment_date', 'Delivery Date'),
        ('invoice_date', 'Invoice Date'),
        ('date_order', 'Date Order'),
    ], string='Sale Over-due Date', default='effective_date', config_parameter='sale_overdue.date')

    def set_values(self):
        if self.env['ir.config_parameter'].sudo().get_param('sale_overdue.date', '') != self.date_overdue_config:
            threaded_calculation = Thread(target=self._procure_recompute_sale_order, args=())
            threaded_calculation.start()
        super(SaleOverDueConfigSettings, self).set_values()


    def _procure_recompute_sale_order(self):
        with api.Environment.manage():
            # As this function is in a new thread, I need to open a new cursor, because the old one may be closed
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            sale_objs = self.env['sale.order'].search([('state', 'in', ('sale', 'done')), ('effective_date', '!=', False)])
            list_fields = ['avg_payment_days', 'overdue_days', 'financing_status', 'late_amount_due', 'payment_term_days',
                                 'overdue_paid_amount', 'indue_paid_amount', 'due_date', 'expected_payments_days']
            for field in list_fields:
                self.env.add_to_compute(self.env['sale.order']._fields[field], sale_objs)
            sale_objs.recompute(list_fields)
            self.env.cr.commit()