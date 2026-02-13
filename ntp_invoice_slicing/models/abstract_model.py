from odoo import api, models, fields, _


class SaleOrderToSlicedInvoicesBase(models.AbstractModel):
    _name = "so.to.sliced.invoices.base"
    _order = "sequence"

    partner_id = fields.Many2one("res.partner", "Partner")
    company_group_code = fields.Many2one(
        "company.group", related="partner_id.company_group_code"
    )
    sequence = fields.Integer("Sequence", copy=True)
    member_id = fields.Many2one(
        "res.partner",
        "Group Member",
        domain="['|', '&', ('id', '=', partner_id), ('group_type', '=', 'head'), '&', ('head_id', '=', partner_id), ('company_group_code', '=', company_group_code), ('company_group_code', '!=', False)]",
    )
    tax_code = fields.Char(related="member_id.vat")

    quota_to_invoice = fields.Float(
        "Quota",
        default=20_000_000,
        copy=True,
    )
    quota_unit = fields.Selection(
        [
            ("amount", "By Amount of Original Invoice"),
            ("percent", "Percent Of Total Amount of Original Invoice"),
            ("balance", "Balance"),
        ],
        "Quota Unit",
        default="amount",
        copy=True,
    )
    max_total_amount_per_invoice = fields.Float(
        "Max Amount Per Invoice / Day",
        copy=True,
        default=20_000_000,
    )

    @api.onchange('quota_unit')
    def onchange_quota_unit(self):
        if self.quota_unit == 'balance':
            self.quota_to_invoice = 0
