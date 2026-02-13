import json
from urllib.parse import urljoin
from odoo import tools, models, api, fields
from odoo.exceptions import UserError
from ..utils.const import hash_content_to_puid


class AccountPayment(models.Model):
    _inherit = "account.payment"

    transfer_content_dict = fields.Text()
    transfer_content = fields.Char(
        "Transfer Content",
        help="Message that will be delivered to customer through bank transfer",
        tracking=True,
    )
    transfer_status = fields.Selection(
        [
            ("prepare", "Prepare"),
            ("transferring", "Transferring"),
            ("transferred", "Transferred"),
            ("reconciled", "Reconciled"),
        ],
        string="Transfer Status",
        default="prepare",
        store=True,
        compute="_compute_transfer_status",
        tracking=True,
    )
    transferred_set = fields.Boolean(defaullt=False)
    puid = fields.Char(
        "Payment Unique Id",
        help="Payment Unique Identifier is embeded into transfer content",
        store=True,
        tracking=True,
        compute="_compute_puid",
    )

    @api.depends("transfer_content")
    def _compute_puid(self):
        for rec in self:
            rec.puid = hash_content_to_puid(rec, rec.transfer_content)

    @api.depends("is_matched", "state")
    def _compute_transfer_status(self):
        for rec in self:
            if rec.state == "draft":
                rec.transfer_status = "prepare"
            if rec.state == "canceled":
                rec.transfer_status = "prepare"
            if rec.state == "posted":
                if rec.is_matched:
                    rec.transferred_set = True
                    rec.transfer_status = "reconciled"
                else:
                    if not rec.transferred_set:
                        # TODO: need to discuss when user undo reconciliation
                        rec.transfer_status = "transferring"
                    else:
                        rec.transfer_status = "transferred"

    def button_set_transferred(self):
        for rec in self:
            if rec.state == "posted":
                rec.transferred_set = True
        self._compute_transfer_status()

    def button_unset_transferred(self):
        for rec in self:
            if rec.state == "posted":
                rec.transferred_set = False
        self._compute_transfer_status()

    def action_generate_transfer_content(self):
        rec = self.env["ntp.transfer.content.generate.wizard"].create(
            {
                "template_type": "payment",
                "model": "account.payment",
                "record_ids": json.dumps(self.ids),
            }
        )
        action = {
            "name": "Generate Transfer Content",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "ntp.transfer.content.generate.wizard",
            "views": [[False, "form"]],
            "context": {},
            "res_id": rec.id,
            "domain": [],
            "target": "new",
        }
        return action

        # for rec in self:
        #     # if rec.is_reconciled:
        #     #     continue
        #     if rec.state == "draft":
        #         continue
        #     if rec.payment_type == "inbound":
        #         continue
        #     if rec.is_move_sent:
        #         continue
        #     try:
        #         content = rec.partner_id.transfer_content_template_id.generate_content(
        #             rec
        #         )
        #         rec.transfer_content = content["transfer_content"]
        #     except Exception as e:
        #         raise UserError(
        #             f"Record: {rec.name}. The configuration for this Payment or Bank Account is not correct. Please check again !"
        #         )

    def action_download_bulk_bank_transfer(self):
        journal_ids = self.mapped("journal_id")
        if len(set(journal_ids)) != 1:
            raise UserError("Cannot download payments from multiple journals")

        data = json.dumps(
            {
                "model_ids": self.ids,
                "model": self._name,
            }
        )
        download_id = (
            self.env["ntp.transfer.content.export.wizard"]
            .sudo()
            .create(
                {
                    "data": data,
                    "export_type": "payment",
                }
            )
        )
        download_id.filename = f"bulk_transfer_download_{download_id.id}.xlsx"
        download_id._compute_url()

        return {
            "type": "ir.actions.act_window",
            "name": "Download",
            "res_model": "ntp.transfer.content.export.wizard",
            "res_id": download_id.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
        }

    def task_recompute_transfer_status(self):
        self.env["account.payment"].search([])._compute_transfer_status()
