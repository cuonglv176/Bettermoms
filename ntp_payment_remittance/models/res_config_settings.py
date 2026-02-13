from odoo import models, fields, api


class NtpPaymentRemittanceConfig(models.TransientModel):
    _inherit = "res.config.settings"

    always_show_internal_transfer_button = fields.Boolean(
        "Always Show Internal Transfer Button"
    )
    show_internal_transfer_button_from = fields.Selection(
        [
            ("sender", "Sending Journal"),
            ("receiver", "Receiving Journal"),
            ("both", "Both")
        ],
        string="Show Button At",
        default="sender"
    )
    internal_transfer_patterns = fields.Text(
        "Internal Transfer Patterns",
        default="(.+)?(Internal(\s+)?Transfer|Transfer(\s+)?To)(.+)?",
        help="when always_show_internal_transfer_button is disabled, this will define pattern to show up button",
    )

    @api.model
    def get_values(self):
        res = super(NtpPaymentRemittanceConfig, self).get_values()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        res.update(
            always_show_internal_transfer_button=get_param(
                "ntp_payment_remittance.always_show_internal_transfer_button"
            ),
            internal_transfer_patterns=get_param(
                "ntp_payment_remittance.internal_transfer_patterns"
            ),
            show_internal_transfer_button_from=get_param(
                "ntp_payment_remittance.show_internal_transfer_button_from"
            ),
        )
        return res

    def set_values(self):
        super(NtpPaymentRemittanceConfig, self).set_values()
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param(
            "ntp_payment_remittance.always_show_internal_transfer_button",
            self.always_show_internal_transfer_button,
        )
        set_param(
            "ntp_payment_remittance.internal_transfer_patterns",
            self.internal_transfer_patterns,
        )
        set_param(
            "ntp_payment_remittance.show_internal_transfer_button_from",
            self.show_internal_transfer_button_from,
        )
