from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def __get_bank_statements_available_sources(self):
        rslt = super(AccountJournal, self).__get_bank_statements_available_sources()
        rslt.append(("bank_sms", _("Bank Sms Mail Auto-Sync")))
        return rslt

    @api.model
    def _get_statement_creation_possible_values(self):
        values = super(AccountJournal, self)._get_statement_creation_possible_values()
        values += [('custom', "Custom Create New Statements")]
        return values

    bank_sms_id = fields.Many2one("bank.sms", ondelete="set null")
    monthly_statement_start_date = fields.Integer("Date To Create Statement", default=1)
    bank_statement_creation_custom = fields.Char(
        "Custom Start Date For New Statement",
        default=1,
        help="Example: 1,11 means create new statement at 1st and 11st of month => 1-10, and 11-end. So if transaction in 3rd will be in statement which has start date is 1st",
    )
    bank_statement_creation_groupby = fields.Selection(selection=_get_statement_creation_possible_values,
                                               help="Defines when a new bank statement will be created when fetching "
                                                    "new transactions from your bank account.",
                                               default='month',
                                               string='Creation of Bank Statements')

    @api.constrains('bank_statement_creation_custom')
    def validate_bank_statement_creation_custom(self):
        for rec in self:
            if rec.bank_statement_creation_groupby == 'custom':
                if not rec.bank_statement_creation_custom:
                    raise UserError("Custom Start Date For New Statement is required !!")
                try:
                    days = [int(x) for x in rec.bank_statement_creation_custom.split(",")]
                    if not len(days):
                        raise UserError("when choosing custom, at least 1 day need to input")
                    valid_days = [28 >= x >=1 for x in days]
                    if not all(valid_days):
                        raise UserError("some days not valid, valid value from 1-28")
                except:
                    raise UserError("Custom Start Date For New Statement not valid")

    @api.constrains("monthly_statement_start_date")
    def _check_monthly_statement_start_date(self):
        if not self.bank_sms_id:
            return
        if 1 <= self.monthly_statement_start_date <= 28:
            return
        raise ValidationError(
            _("Please choose 'Date To Create Statement' between 1-28.")
        )

    @api.model
    def _cron_fetch_sms_transactions(self):
        for journal in self.search(
            [
                ("bank_statements_source", "=", "bank_sms"),
                ("bank_sms_id", "!=", False),
            ]
        ).filtered(lambda x: x.bank_sms_id.auto_sync):
            try:
                journal.with_context(cron=True).manual_sms_sync()
                # for cron jobs it is usually recommended to commit after each iteration, so that a later error or job timeout doesn't discard previous work
                self.env.cr.commit()
            except Exception as e:
                journal.message_post(boyd=f"Error: {e}")

    def manual_sms_sync(self):
        self.ensure_one()
        if self.bank_sms_id and self.bank_statements_source == "bank_sms":
            return self.bank_sms_id._fetch_transactions(journal=self)
