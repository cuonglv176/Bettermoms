from collections import OrderedDict

from jinja2 import Template
from odoo import api, fields, models
from odoo.exceptions import UserError
from ..utils.normalize import normalize_string


class TransferContentTemplate(models.Model):
    _name = "ntp.transfer.content.template"
    _description = "Transfer Content Template"

    name = fields.Char("Name")
    version = fields.Char("Version")
    template_type = fields.Selection(
        [
            ("payment", "Payment"),
            ("payslip", "Payslip"),
        ],
        string="Template Type",
        default="payment")
    delimiter = fields.Char(default="..")
    transfer_content = fields.Char(
        "Template",
        default="{{DELIMITER}}{{VERSION}}{{DELIMITER}}{{SENDER}}{{DELIMITER}}{{RECEIVER}}{{DELIMITER}}{{PAYMENT_ID}}{{DELIMITER}}{{ACCOUNTING_MONTH}}{{DELIMITER}}{{BILL_REF}}",
    )
    config = fields.Text(
        default="""
DELIMITER:=lambda record, config: config.delimiter
VERSION:=lambda record, config: config.version
SENDER:=lambda record, config: "NTPTECH"
RECEIVER:=lambda record, config: record.partner_id.company_group_code.name or ""
PAYMENT_ID:=lambda record, config: record.name or ""
ACCOUNTING_MONTH:=lambda record, config: record.date.strftime("%Y%b") if record.date else ""
BILL_REF:=lambda record, config: record.ref
    """.strip()
    )
    # partner_bank_ids = fields.One2many(
    #     "res.partner.bank", "transfer_content_template_id"
    # )
    partner_ids = fields.One2many(
        "res.partner", "transfer_content_template_id", domain="[('parent_id', '=', False)]"
    )

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, "%s - %s - %s" % (record.name, record.template_type, record.version)))

        return result

    def action_generate_content(self, record):
        if self.template_type == 'payslip':
            return self.generate_content_payslip(record)
        if self.template_type == 'payment':
            return self.generate_content_payment(record)

    def generate_content_payment(self, payment):
        def get_eval():
            eval_dict = {}
            for config in self.config.split("\n"):
                if ":=" in config:
                    key, func = config.strip().split(":=")
                    eval_dict[key] = eval(func)
            return eval_dict

        eval_dict = get_eval()

        result = {
            "benificiary_account": "",
            "transfer_amount": "",
            "bank_code": "",
            "benificiary_name": "",
            "transfer_content": "",
            "tax_code": "",
            "tax_reference": "",
            "template_id": self.id
        }
        repr_data = {k: v(payment, self) for k, v in eval_dict.items()}

        # fmt: off
        if payment.partner_bank_id:
            partner_bank = payment.partner_bank_id
            result["benificiary_account"] = partner_bank.acc_number or ""
            result["bank_code"] = (
                partner_bank.bank_branch_id.citad_code or ""
            )
            if partner_bank.acc_holder_name:
                result["benificiary_name"] = partner_bank.acc_holder_name
        if not result["benificiary_account"] or not result["bank_code"] or not result["benificiary_name"]:
            raise UserError(f"Partner of Payment '{payment.name}' not have Bank Account or Bank Account not configured properly")

        # fmnt: on
        result["transfer_amount"] = payment.amount
        keys = ["transfer_content"]

        for k in keys:
            result[k] = normalize_string(Template(self[k] or "").render(repr_data))

        return result

    def generate_content_payslip(self, payslip):
        def get_eval():
            eval_dict = {}
            for config in self.config.split("\n"):
                if ":=" in config:
                    key, func = config.strip().split(":=")
                    eval_dict[key] = eval(func)
            return eval_dict

        eval_dict = get_eval()

        result = {
            "benificiary_account": "",
            "transfer_amount": "",
            "bank_code": "",
            "benificiary_name": "",
            "transfer_content": "",
            "tax_code": "",
            "tax_reference": "",
            "template_id": self.id
        }
        repr_data = {k: v(payslip, self) for k, v in eval_dict.items()}

        # fmt: off
        if payslip.employee_id.bank_account_id:
            partner_bank = payslip.employee_id.bank_account_id
            result["benificiary_account"] = partner_bank.acc_number or ""
            result["bank_code"] = (
                partner_bank.bank_branch_id.citad_code or ""
            )
            if partner_bank.acc_holder_name:
                result["benificiary_name"] = partner_bank.acc_holder_name
        if not result["benificiary_account"] or not result["bank_code"] or not result["benificiary_name"]:
            raise UserError(f"Employee '{payslip.employee_id.name}' not have Bank Account or Bank Account not configured properly")
        # fmnt: on
        result["transfer_amount"] = payslip.net_wage
        keys = ["transfer_content"]

        for k in keys:
            result[k] = normalize_string(Template(self[k] or "").render(repr_data))

        return result
