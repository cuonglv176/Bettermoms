# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, SUPERUSER_ID, api, _, fields
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

class MailComposeMessage(models.TransientModel):

    _name = "send.multiple.mail"
    _description = "Send Multiple Payslip"

    def get_default_template_id(self):
        template_id = self.env['ir.model.data']._xmlid_lookup('bi_mass_payslip_by_email.email_template_edi_hr_payroll')[
            2]
        return template_id or False
    template_id = fields.Many2one('mail.template', domain=[('model_id.model', '=', 'hr.payslip')], default=get_default_template_id)



    def send_muliple_mail(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids')
        super_user = self.env['res.users'].browse(self.env['res.users']._context["uid"])
        for a_id in active_ids:
            hr_payslip_brw = self.env['hr.payslip'].browse(a_id)
            for employee in hr_payslip_brw.employee_id:
                employee_email = employee.work_email
                if not employee_email:
                    raise UserError(_('%s Employee has no email id please enter email address')
                            % (hr_payslip_brw.employee_id.name)) 
                else:
                    email_template_obj = template_id = self.template_id
                    if not self.template_id:
                        template_id = self.env['ir.model.data']._xmlid_lookup('bi_mass_payslip_by_email.email_template_edi_hr_payroll')[2]
                        email_template_obj = self.env['mail.template'].browse(template_id)
                    if template_id:
                        values = email_template_obj.generate_email(a_id, fields=['subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'email_cc', 'reply_to', 'scheduled_date'])
                        values['email_from'] = super_user.partner_id.email
                        values['author_id'] = super_user.partner_id.id
                        values['email_to'] = employee_email
                        ir_attachment_obj = self.env['ir.attachment']
                        vals = {
                                'name' : values['attachments'][0][0],
                                'type' : 'binary',
                                'store_fname': values['attachments'][0][0],
                                'datas' : values['attachments'][0][1],
                                'res_id' : a_id,
                                'res_model' : 'hr.payslip',
                        }
                        attachment_id = ir_attachment_obj.sudo().create(vals)
                        mail_mail_obj = self.env['mail.mail']
                        values.pop('attachments')
                        msg_id = mail_mail_obj.sudo().create(values)
                        msg_id.attachment_ids=[(6,0,[attachment_id.id])]
                        if msg_id:
                            mail_mail_obj.sudo().send([msg_id])
        return True
            
