import json
from odoo import models, fields, api
from odoo.exceptions import UserError


class TransferContentGenerateWizard(models.AbstractModel):
    _name = "ntp.transfer.content.generate.base"

    model = fields.Char()
    record_ids = fields.Text()
    template_type = fields.Selection(
        [
            ("payment", "Payment"),
            ("payslip", "Payslip"),
        ],
        string="Template Type",
    )
    transfer_content_template_id = fields.Many2one(
        "ntp.transfer.content.template",
        "Template",
        domain="[('template_type', '=', template_type)]",
    )
    override_option = fields.Selection(
        [
            ("fill_when_empty", "Update if not set"),
            ("override", "Override exising"),
        ],
        string="Override Option",
        default="fill_when_empty",
    )


class TransferContentGenerateWizard(models.TransientModel):
    _name = "ntp.transfer.content.generate.wizard"
    _inherit = "ntp.transfer.content.generate.base"

    def generate_transfer_content(self):
        model = self.model
        record_ids = json.loads(self.record_ids)
        records = self.env[model].browse(record_ids)

        for record in records:
            try:
                # fmt: off
                if getattr(record, 'partner_id', None) and record.partner_id.transfer_content_template_id:
                    # if partner_id in this record and is configured transfer_content_template_id
                    content_dict = record.partner_id.transfer_content_template_id.action_generate_content(record)
                else:
                    content_dict = self.transfer_content_template_id.action_generate_content(record)
                if self.override_option == 'override':
                    record.transfer_content = content_dict['transfer_content']
                elif self.override_option == 'fill_when_empty' and not record.transfer_content:
                    record.transfer_content = content_dict['transfer_content']
                record.transfer_content_dict = json.dumps(content_dict)
                # fmt: on
            except Exception as e:
                raise UserError(
                    f"Record: {record.name}. The configuration to generate transfer content is not correct. Please check again !\n{e}"
                )
