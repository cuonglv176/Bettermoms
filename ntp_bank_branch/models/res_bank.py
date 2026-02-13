from odoo import models, fields, api, _


class ResBank(models.Model):
    _inherit = "res.bank"

    short_name = fields.Char("Short Name")
    bank_branch_ids = fields.One2many("ntp.bank.branch", "bank_id")
    version = fields.Char()