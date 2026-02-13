from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    transfer_content_template_id = fields.Many2one("ntp.transfer.content.template")
