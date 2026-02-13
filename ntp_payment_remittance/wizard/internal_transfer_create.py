from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class InternalTransferCreate(models.TransientModel):
    _name = "internal.transfer.create"
    _description = "Create Internal Transfer Wizard"

    # link to account.move
    currency_id = fields.Many2one(
        "res.currency", related="statement_line_id.currency_id"
    )
    journal_id = fields.Many2one("account.journal", related="statement_id.journal_id")
    statement_id = fields.Many2one("account.bank.statement")
    statement_line_id = fields.Many2one(
        "account.bank.statement.line", domain="[('statement_id', '=', statement_id)]"
    )
    date = fields.Date(related="statement_line_id.date")
    amount = fields.Monetary(related="statement_line_id.amount")
    payment_ref = fields.Char(related="statement_line_id.payment_ref")

    destination_journal_id = fields.Many2one("account.journal")

    auto_post_when_create = fields.Boolean("Confirm Internal Transfer When Create", default=True,
        help="This will change internal transfer to 'POSTED'.\n"
             "A second payment will be created automatically in the destination journal.")

    def button_create_internal_transfer(self):
        src_statement_line_id = self.statement_line_id
        src_journal_id = self.journal_id
        dst_journal_id = self.destination_journal_id
        payment_type = 'outbound' if self.amount < 0 else 'inbound'
        AccountPayment = self.env['account.payment']
        data_to_create = {
            'is_internal_transfer': True,
            'payment_type': payment_type,
            'amount': abs(self.amount),
            'currency_id': self.currency_id.id,
            'date': self.date,
            'ref': self.payment_ref,
            'journal_id': src_journal_id.id,
            'destination_journal_id': dst_journal_id.id
        }
        internal_transfer = AccountPayment.create(data_to_create)
        if self.auto_post_when_create:
            internal_transfer.action_post()
            if payment_type == 'outbound':
                ref = "Stmt {} / {} -> {} / Internal Transfer".format(src_statement_line_id.move_id.name, internal_transfer.name, internal_transfer.paired_internal_transfer_payment_id.name)
            else:
                ref = "Stmt {} / {} -> {} / Internal Transfer".format(src_statement_line_id.move_id.name, internal_transfer.paired_internal_transfer_payment_id.name, internal_transfer.name)
            internal_transfer.update({"ref": ref})
            internal_transfer.paired_internal_transfer_payment_id.update({"ref": ref})

        # auto change to set internal transfer created once, so not showing button to create it
        src_statement_line_id.internal_transfer_created = True

        return {
            'res_model': 'account.payment',
            'res_id': internal_transfer.id,
            'type': 'ir.actions.act_window',
            'context': {},
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current'
        }
