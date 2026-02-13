import logging
from odoo import models, fields, api, tools, _


logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    ready_to_invoice_from_so = fields.Boolean(
        compute="_compute_ready_to_invoice_from_so", store=False
    )

    @api.depends("state", "sale_id.invoice_status")
    def _compute_ready_to_invoice_from_so(self):
        for rec in self:
            rec.ready_to_invoice_from_so = False
            try:
                if rec.sale_id:
                    invoice_status = rec.sale_id.invoice_status
                    # Waiting / Ready / Done => show create invoice button
                    if invoice_status == "to invoice" and rec.state in ["confirmed", "assigned", "done"]:
                        # this means, so can make some invoices and current stock picking form related to future invoices
                        rec.ready_to_invoice_from_so = True
            except Exception as e:
                logger.error(e)

    def button_notify_to_create_invoice(self):
        # to notify user to create invoice (which is accountant -> set it settings)
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
            body += f' <b>please issue Invoice for <a href=/web#model=sale.order&id=={self.sale_id.id} class="o_mail_redirect" data-oe-id="{self.sale_id.id}" data-oe-model="sale.order" target="_blank">{self.sale_id.name}</a></b>'
            self.message_post(
                body=body,
                subtype_xmlid="mail.mt_comment",
                partner_ids=partner_ids,
                message_type="comment",
            )
