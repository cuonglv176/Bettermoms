from odoo import models, fields, api


class ResConfig(models.TransientModel):
    _inherit = "res.config.settings"

    payment_plan_by = fields.Selection(
        [("week", "Week"), ("month", "Month")], default="week"
    )
    payment_plan_pay_date_of_month = fields.Integer(default=20)
    payment_plan_pay_date_of_week = fields.Selection(
        [
            ("0", "Every Monday"),
            ("1", "Every Tuesday"),
            ("2", "Every Wednesday"),
            ("3", "Every Thursday"),
            ("4", "Every Friday"),
            ("5", "Every Saturday"),
            ("6", "Every Sunday"),
        ],
        default="5",
    )

    @api.model
    def get_values(self):
        res = super(ResConfig, self).get_values()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        res.update(
            payment_plan_by=get_param("ntp_payable_management.payment_plan_by"),
            payment_plan_pay_date_of_month=get_param(
                "ntp_payable_management.payment_plan_pay_date_of_month"
            ),
            payment_plan_pay_date_of_week=get_param(
                "ntp_payable_management.payment_plan_pay_date_of_week"
            ),
        )
        return res

    def set_values(self):
        super(ResConfig, self).set_values()
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param("ntp_payable_management.payment_plan_by", self.payment_plan_by)
        set_param(
            "ntp_payable_management.payment_plan_pay_date_of_month",
            self.payment_plan_pay_date_of_month,
        )
        set_param(
            "ntp_payable_management.payment_plan_pay_date_of_week",
            self.payment_plan_pay_date_of_week,
        )
