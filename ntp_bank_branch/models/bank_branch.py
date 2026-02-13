from odoo import models, fields, api, _


class BankBranch(models.Model):
    _name = "ntp.bank.branch"

    bank_id = fields.Many2one("res.bank")
    citad_code = fields.Char("Code")
    region_name = fields.Char("Region")
    citad_bank_branch = fields.Char("Branch Name")
    detail_info = fields.Text("Detail")
    active = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for record in self:
            result.append(
                (
                    record.id,
                    "%s - %s" % (record.citad_bank_branch, record.citad_code),
                )
            )
        return result

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = args or []
        recs = self.browse()
        if not recs:
            recs = self.search(
                [
                    "|",
                    "|",
                    ("citad_bank_branch", operator, name),
                    ("citad_code", operator, name),
                    ("detail_info", operator, name),
                ]
                + args,
                limit=limit,
            )
        return recs.name_get()
