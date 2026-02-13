from odoo import models, fields, api, tools, _


class AccountMove(models.Model):
    _inherit = "account.move"

    draft_payment_ids = fields.One2many("account.payment", "draft_account_move_id")
    draft_payment_count = fields.Integer(compute="_compute_draft_payment_data")
    draft_payment_show = fields.Boolean(compute="_compute_draft_payment_data")

    def _compute_draft_payment_data(self):
        for rec in self:
            rec.draft_payment_count = len(rec.draft_payment_ids)
            rec.draft_payment_show = False
            if (
                rec.move_type
                in ["in_invoice", "in_receipt", "out_invoice", "out_receipt"]
                and rec.draft_payment_count != 0
            ):
                rec.draft_payment_show = True

    def button_open_draft_payments(self):
        context = self.env.context.copy()
        action = {
            "name": _("Draft Payment"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "account.payment",
            "view_mode": "tree,form",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [("draft_account_move_id", "=", self.id)],
            "target": "current",
        }
        return action

    def action_post(self):
        ret = super().action_post()
        if not self.payment_id:
            if self.payment_state not in [
                "paid",
                "invoicing_legacy",
            ] and self.move_type in ["in_invoice", "in_receipt"]:
                # do open register payment popup windows
                action_register = self.action_register_payment()
                action_register["context"]["default_create_draft_payment"] = True
                return action_register
        else:
            return ret
