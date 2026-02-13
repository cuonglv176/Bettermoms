from odoo import models, fields, api, _


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    bank_branch_id = fields.Many2one(
        "ntp.bank.branch", "Branch", domain="[('bank_id', '=', bank_id)]"
    )
    bank_branch_detail = fields.Text("Branch Detail", related="bank_branch_id.detail_info")

    @api.onchange("bank_id")
    def onchange_bank_id(self):
        self.bank_branch_id = False
