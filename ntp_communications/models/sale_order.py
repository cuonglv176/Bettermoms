from odoo import models, fields, api, tools, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def button_notify_to_create_invoice(self):
        try:
            users = (
                self.env["res.config.settings"]
                .search([])[-1]
                .users_notify_to_create_invoice
            )
        except IndexError:
            users = (
                self.env["res.config.settings"]
                .create({})
                .users_notify_to_create_invoice
            )
        if users:
            body = ""
            mentioned = []
            partner_ids = []
            for user in users:
                mentioned.append(
                    f'<a href=/web#model=res.partner&id={user.partner_id.id} class="o_mail_redirect" data-oe-id="{user.partner_id.id}" data-oe-model="res.partner" target="_blank">@{user.partner_id.name}</a>'
                )
                partner_ids.append(user.partner_id.id)
            body += ", ".join(mentioned)
            body += f' <b>please issue Invoice for this Sale Order</b>'
            self.message_post(
                body=body,
                subtype_xmlid="mail.mt_comment",
                partner_ids=partner_ids,
                message_type="comment",
            )
