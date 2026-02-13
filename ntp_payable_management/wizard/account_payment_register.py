from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    create_draft_payment = fields.Boolean("Draft Payment Only", default=True)

    def _post_payments(self, to_process, edit_mode=False):
        if not self.create_draft_payment:
            super(AccountPaymentRegister, self)._post_payments(to_process, edit_mode)

    def _reconcile_payments(self, to_process, edit_mode=False):
        if not self.create_draft_payment:
            super(AccountPaymentRegister, self)._reconcile_payments(
                to_process, edit_mode
            )

    def _create_payments(self):
        if not self.create_draft_payment:
            payments = super(AccountPaymentRegister, self)._create_payments()
            return payments
        else:
            move_ids = self.env.context["active_ids"]
            partner_ids = (
                self.env["account.move"].browse(move_ids).mapped("partner_id").ids
            )
            if len(partner_ids) != len(move_ids):
                raise UserError(
                    f"Not support create multiple draft payments for same partner. It could make incorrect relation between draft payments and bill/invoices"
                )
            #
            # add draft relation
            self._cr.execute("SAVEPOINT account_payment_draft_creation")
            payments = super(AccountPaymentRegister, self)._create_payments()
            if len(payments) != len(self.env.context["active_ids"]):
                self._cr.execute("ROLLBACK TO SAVEPOINT account_payment_draft_creation")
                raise UserError(
                    f"Number of Draft Payment Created ({len(payments)}) != Number of Selected Bills ({len(self.env.context['active_ids'])})"
                )
            #
            # already make sure that payments created from vendors not duplicated
            for payment in payments:
                # json.loads(self.env['account.move'].browse(11685).tax_totals_json)['amount_total']
                matched = False
                for move_id in move_ids:
                    move = self.env["account.move"].browse(move_id)
                    if payment.partner_id == move.partner_id:
                        payment.draft_account_move_id = move
                        matched = True
                        break
                if not matched:
                    raise UserError(
                        "Draft Payments Create error. Try to create one by one instead"
                    )
            return payments
