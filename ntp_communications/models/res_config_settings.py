import logging
import json
from odoo import models, fields, api


logger = logging.getLogger(__name__)


class ResConfig(models.TransientModel):
    _inherit = "res.config.settings"

    users_notify_to_create_invoice = fields.Many2many(
        "res.users", string="Users To Notify"
    )

    @api.model
    def get_values(self):
        res = super(ResConfig, self).get_values()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        user_ids = get_param("ntp_communications.users_notify_to_create_invoice")
        try:
            if user_ids:
                user_ids = json.loads(user_ids)
                user_ids = self.env['res.users'].browse(user_ids)
                res.update(users_notify_to_create_invoice=[(6, 0, user_ids.ids)])
        except Exception as e:
            logger.error(e, exc_info=True)
            set_param = self.env["ir.config_parameter"].sudo().set_param
            set_param(
                "ntp_communications.users_notify_to_create_invoice",
                False,
            )
        return res

    def set_values(self):
        super(ResConfig, self).set_values()
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param(
            "ntp_communications.users_notify_to_create_invoice",
            json.dumps(self.users_notify_to_create_invoice.ids),
        )
