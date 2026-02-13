from odoo import models, fields, api


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    # transfer_content_template_id = fields.Many2one("ntp.transfer.content.template", "Transfer Template")
