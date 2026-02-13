import logging
from odoo import fields, api, models, _
from ..utils.const import extract_puid_from_content
from ..utils.misc import truncate_middle

logger = logging.getLogger(__name__)


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    def task_find_partner_from_puid(self):
        statements = (
            self.env["account.bank.statement"]
            .sudo()
            .search([("state", "!=", "confirm")])
        )
        statements.sudo().action_find_partner_from_puid()

    def action_find_partner_from_puid(self):
        for rec in self:
            rec._find_partner_from_puid()

    def _find_partner_from_puid(self):
        self.ensure_one()
        if self.state == "confirm":
            return
#         sql = """
# SELECT DISTINCT
#     st_line.id AS id,
#     st_line.payment_ref as payment_ref,
#     st_line.partner_id AS partner_id,
#     payment.partner_id AS candidate_partner_id
# FROM account_bank_statement_line st_line
#     INNER JOIN account_payment payment ON (
#         COALESCE(st_line.puid, '') != ''
#         AND COALESCE(payment.puid, '') != ''
#         AND POSITION(payment.puid IN st_line.puid) > 0
#     )
# WHERE
#     st_line.partner_id IS NULL
#     AND st_line.statement_id = {statement_id};
#         """
        sql = """
SELECT DISTINCT
    st_line.id AS id,
    st_line.payment_ref as payment_ref,
    st_line.partner_id AS partner_id,
    move.partner_id AS candidate_partner_id
FROM account_bank_statement_line st_line
    INNER JOIN account_move move ON (
        COALESCE(st_line.puid, '') != ''
        AND COALESCE(move.name, '') != ''
        AND move.state = 'posted'
        AND POSITION(move.name IN st_line.puid) > 0
    )
WHERE
    st_line.partner_id IS NULL
    AND st_line.is_reconciled = false
    AND st_line.statement_id = {statement_id};
        """
        query = sql.format(statement_id=self.id)
        self._cr.execute(query)
        result = self._cr.dictfetchall()
        st_line_updatable = {}
        result_msg = []
        for row in result:
            if row["id"] not in st_line_updatable:
                # init
                st_line_updatable[row["id"]] = {
                    "partner_ids": [],
                    "payment_ref": row["payment_ref"],
                }
            st_line_updatable[row["id"]]["partner_ids"].append(
                row["candidate_partner_id"]
            )
        statement_line = self.env["account.bank.statement.line"]
        for st_line_id, data in st_line_updatable.items():
            if len(set(data["partner_ids"])) == 1:
                partner_id = data["partner_ids"][0]
                statement_line.browse(st_line_id).update({"partner_id": partner_id})
                result_msg.append(
                    "Updated OK: " + truncate_middle(data["payment_ref"], 100)
                )
            elif len(set(data["partner_ids"])) > 1:
                # duplicated
                result_msg.append(
                    "!! <span style='color: red'>Duplicated Partner</span>: "
                    + truncate_middle(data["payment_ref"], 100)
                )
        if result_msg:
            self.message_post(body="<br/>".join(result_msg))


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    puid = fields.Char("PUID", store=True, compute="_compute_puid")

    @api.depends("payment_ref")
    def _compute_puid(self):
        for rec in self:
            if not rec.payment_ref:
                continue
            rec.puid = ",".join(extract_puid_from_content(rec, rec.payment_ref))
