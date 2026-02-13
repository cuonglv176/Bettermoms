import logging

from odoo import models, api, fields, SUPERUSER_ID, _
from datetime import date, timedelta

from odoo.exceptions import UserError


logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    draft_account_move_id = fields.Many2one("account.move")

    plan_week_id = fields.Many2one(
        "account.payment.plan.week",
        string="Plan Week",
        index=True,
        tracking=True,
        compute="_compute_plan_week_id",
        readonly=False,
        store=True,
        copy=False,
        group_expand="_read_group_plan_week_ids",
        ondelete="set null",
    )
    plan_month_id = fields.Many2one(
        "account.payment.plan.month",
        string="Plan Month",
        index=True,
        tracking=True,
        compute="_compute_plan_month_id",
        readonly=False,
        store=True,
        copy=False,
        group_expand="_read_group_plan_month_ids",
        ondelete="set null",
    )

    payment_score = fields.Float(
        "Payment Score", digits=(2, 1), compute="_compute_payment_score", store=True
    )
    payment_late_days = fields.Integer(compute="_compute_payment_late_days")
    # NOTE: this is just copy value from account.move to account.payment to use it in graph
    paid_date = fields.Date("Paid Date", store=True, compute="_compute_paid_date")

    def write(self, vals):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        _by = get_param("ntp_payable_management.payment_plan_by")
        _wd = get_param("ntp_payable_management.payment_plan_pay_date_of_week")
        _md = get_param("ntp_payable_management.payment_plan_pay_date_of_month") or 1

        update_plan = (
            True if "plan_month_id" in vals or "plan_week_id" in vals else False
        )
        ignore_state_check = self.env.context.get("ignore_state_check", False)
        if update_plan and not ignore_state_check:
            for rec in self:
                # only movable entry which is not posted yet
                if rec.state != "draft":
                    raise UserError("Cannot plan payment which is not Draft")
        do_update_date = False
        if set(vals) == set(["plan_month_id"]):
            target_date = (
                self.env["account.payment.plan.month"]
                .browse(vals["plan_month_id"])
                .target_date
            )
            plan_week_id = self.env[
                "account.payment.plan.week"
            ].get_or_create_from_target_date(target_date=target_date)
            vals.update({"plan_week_id": plan_week_id.id})
            do_update_date = True
        elif set(vals) == set(["plan_week_id"]):
            plan_month_id = (
                self.env["account.payment.plan.week"]
                .browse(vals["plan_week_id"])
                .plan_month_id
            )
            vals.update({"plan_month_id": plan_month_id.id})
            do_update_date = True
        write_result = super().write(vals)
        if do_update_date:
            self.onchange_plan_week_id()
        return write_result

    @api.onchange("date")
    def onchange_date(self):
        self._compute_plan_week_id()
        self._compute_plan_month_id()
        self._compute_paid_date()

    @api.onchange("plan_week_id")
    def onchange_plan_week_id(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        _by = get_param("ntp_payable_management.payment_plan_by")
        _wd = get_param("ntp_payable_management.payment_plan_pay_date_of_week")
        _md = get_param("ntp_payable_management.payment_plan_pay_date_of_month") or 1
        # check new date following config setting
        for rec in self:
            target_date = rec.plan_week_id.target_date
            rec.date = (
                target_date
                - timedelta(days=target_date.weekday())
                + timedelta(days=int(_wd))
            )

    @api.depends("date")
    def _compute_plan_week_id(self):
        for rec in self:
            if rec.date == False:
                rec.plan_week_id = False
            else:
                rec.plan_week_id = self.env[
                    "account.payment.plan.week"
                ].get_or_create_from_target_date(rec.date, fold=False)

    @api.depends("plan_week_id")
    def _compute_plan_month_id(self):
        for rec in self:
            if rec.plan_week_id:
                rec.plan_month_id = rec.plan_week_id.plan_month_id
            else:
                rec.plan_month_id = False

    @api.depends("date")
    def _compute_paid_date(self):
        for rec in self:
            rec.paid_date = rec.date

    def _compute_payment_late_days(self):
        for rec in self:
            rec.payment_late_days = 0
            if rec.transfer_status != "reconciled":
                today = fields.Date.today()
                rec.payment_late_days = (rec.date - today).days

    def _compute_payment_score(self):
        for rec in self:
            rec.payment_score = 0

    @api.model_create_multi
    @api.returns("self", lambda value: value.id)
    def create(self, vals_list):
        records = super().create(vals_list)
        # TODO: set default date
        return records

    @api.model
    def _read_group_plan_week_ids(self, plans, domain, order):
        # retrieve team_id from the context and write the domain
        # - ('id', 'in', plans.ids): add columns that should be present
        # - OR ('fold', '=', False): add default columns that are not folded
        # - OR ('team_ids', '=', team_id), ('fold', '=', False) if team_id: add team columns that are not folded
        team_id = self._context.get("default_team_id")
        if team_id:
            search_domain = ["|", ("id", "in", plans.ids), ("fold", "=", False)]
        else:
            search_domain = ["|", ("id", "in", plans.ids), ("fold", "=", False)]

        # perform search
        plan_week_ids = plans._search(
            search_domain, order=order, access_rights_uid=SUPERUSER_ID
        )
        # self.env["account.payment.plan.week"].search([]).auto_fold_today()
        plans = plans.browse(plan_week_ids)
        return plans

    @api.model
    def _read_group_plan_month_ids(self, plans, domain, order):
        # retrieve team_id from the context and write the domain
        # - ('id', 'in', plans.ids): add columns that should be present
        # - OR ('fold', '=', False): add default columns that are not folded
        # - OR ('team_ids', '=', team_id), ('fold', '=', False) if team_id: add team columns that are not folded
        team_id = self._context.get("default_team_id")
        if team_id:
            search_domain = ["|", ("id", "in", plans.ids), ("fold", "=", False)]
        else:
            search_domain = ["|", ("id", "in", plans.ids), ("fold", "=", False)]

        # perform search
        plan_month_ids = plans._search(
            search_domain, order=order, access_rights_uid=SUPERUSER_ID
        )
        # self.env["account.payment.plan.month"].search([]).auto_fold_today()
        plans = plans.browse(plan_month_ids)
        return plans

    def button_open_bill_source(self):
        context = self.env.context.copy()
        action = {
            "name": _("Bill Source"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "account.move",
            "view_mode": "form",
            "context": {"create": False},
            "res_id": self.draft_account_move_id.id,
            # "views": [[False, "tree"], [False, "form"]],
            # "domain": [("id", "=", self.draft_account_move_id.id)],
            "target": "current",
        }
        return action

    def task_update_payment_plan(self):
        for rec in (
            self.env["account.payment"]
            .with_context(ignore_state_check=True)
            .sudo()
            .search([])
        ):
            sql = "update account_payment set plan_week_id = {_1}, plan_month_id = {_2} where id = {_3}"
            week = self.env["account.payment.plan.week"].get_or_create_from_target_date(
                rec.date, fold=False
            )
            week_id = week.id
            month_id = week.plan_month_id.id
            sql = sql.format(_1=week_id, _2=month_id, _3=rec.id)
            self._cr.execute(sql)
        self._cr.commit()

    def button_open_update_bank_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Update Bank Account",
            "res_model": "account.payment.update.bank",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payment_id": self.id
            }
        }
