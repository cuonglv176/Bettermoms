import logging
from odoo import models, api, fields, SUPERUSER_ID, tools
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


logger = logging.getLogger(__name__)


class AccountPaymentPlanBase(models.AbstractModel):
    _name = "account.payment.plan.base"
    _description = "Account Payment Plans"
    _rec_name = "name"
    _order = "sequence, name, id"
    _sql_constraints = [
        (
            "name_uniq",
            "UNIQUE (name)",
            "You can not have two record with the same name!",
        ),
    ]

    name = fields.Char(
        "Plan Name",
        readonly=True,
        store=True,
        compute="_compute_data",
    )
    sequence = fields.Integer(
        "Sequence",
        default=1,
        help="Used to order plans. Lower is better.",
        store=True,
        readonly=True,
        compute="_compute_data",
    )
    fold = fields.Boolean(
        "Folded",
        help="This plan is folded in the kanban view when there are no records in that plan to display.",
    )
    target_date = fields.Date(
        "Target Date", default=lambda self: fields.Date.today(), required=True
    )
    target_week = fields.Char("Target Week", compute="_compute_target")
    target_month = fields.Char("Target Month", compute="_compute_target")
    target_quarter = fields.Char("Target Quarter", compute="_compute_target")
    target_year = fields.Char("Target Year", compute="_compute_target")

    @api.onchange("target_date")
    def _compute_target(self):
        for rec in self:
            rec.target_week = (
                rec.target_month
            ) = rec.target_quarter = rec.target_year = ""
            if rec.target_date:
                rec.target_week = rec.target_date.strftime("W%W")
                rec.target_month = rec.target_date.strftime("%b")
                rec.target_quarter = "Q" + str(rec.target_date.month // 4 + 1)
                rec.target_year = str(rec.target_date.year)

    def button_toogle_fold(self):
        for rec in self:
            rec.fold = False if rec.fold else True

    def get_plan_time(self, type="week"):
        def get_number_compare(d: date):
            if type == "week":
                return d.year * 100 + d.isocalendar()[1]
            return d.year * 100 + d.month

        today = fields.Date.today()
        today_number = get_number_compare(today)
        my_number = get_number_compare(self.target_date)
        if today_number == my_number:
            return "current"
        if today_number > my_number:
            return "past"
        return "future"

    def _auto_sort(self, type):
        def get_number_compare(d: date):
            if type == "week":
                return d.year * 100 + d.isocalendar()[1]
            return d.year * 100 + d.month

        for rec in self:
            sequence = get_number_compare(rec.target_date)
            rec.sequence = sequence

    def _auto_fold_today(self, type):
        for rec in self:
            plan_time = rec.get_plan_time(type)
            if plan_time == "current":
                rec.fold = False
            if plan_time == "past":
                rec.fold = True
            if plan_time == "future":
                rec.fold = False


class AccountPaymentPlan(models.Model):
    _name = "account.payment.plan.week"
    _inherit = "account.payment.plan.base"
    _description = "Account Payment Plans Week"

    payment_ids = fields.One2many("account.payment", "plan_week_id")
    budget_in = fields.Monetary("Budget In")
    budget_out = fields.Monetary("Budget Out")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    plan_month_id = fields.Many2one("account.payment.plan.month")

    def name_get(self):
        today = fields.Date.today()
        result = []
        # fmt: off
        for record in self:
            if record.target_date.year == today.year:
                diff = today.isocalendar()[1] - record.target_date.isocalendar()[1]
                if diff < 0:
                    diff = f'(+{abs(diff)})'
                elif diff > 0:
                    diff = f'(-{abs(diff)})'
                else:
                    diff = '(0)'
                result.append(
                    (record.id, "%s %s" % (record.name, diff,))
                )
            else:
                result.append(
                    (record.id, "%s" % (record.name))
                )
        # fmt: on
        return result

    @api.depends("target_date")
    def _compute_data(self):
        for rec in self:
            if rec.target_date:
                name = "{} - W{}".format(
                    rec.target_date.year, rec.target_date.strftime("%W")
                )
                rec.name = name
                # sequence = year * 100 + week_no
                rec.sequence = (
                    rec.target_date.year * 100 + rec.target_date.isocalendar()[1]
                )
            else:
                rec.sequence = 1
                rec.name = f"Draft Plan Week"

    @api.model_create_multi
    @api.returns("self", lambda value: value.id)
    def create(self, vals_list):
        records = super().create(vals_list)
        records.fix_target_date()
        return records

    def fix_target_date(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        _by = get_param("ntp_payable_management.payment_plan_by")
        _wd = get_param("ntp_payable_management.payment_plan_pay_date_of_week")
        _md = get_param("ntp_payable_management.payment_plan_pay_date_of_month") or 1

        for record in self:
            target_date = record.target_date
            start = target_date - timedelta(days=target_date.weekday())
            plan_target_date = start + timedelta(days=int(_wd))
            record["target_date"] = plan_target_date

    @api.model
    def plan_create(self, *args):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        _by = get_param("ntp_payable_management.payment_plan_by")
        _wd = get_param("ntp_payable_management.payment_plan_pay_date_of_week")
        _md = get_param("ntp_payable_management.payment_plan_pay_date_of_month") or 1

        plan_ahead_week = 24
        today = fields.Date.today()
        start_day = date(today.year, 1, 1)
        end_day = today + timedelta(weeks=plan_ahead_week)
        _date = (
            start_day - timedelta(days=start_day.weekday()) + timedelta(days=int(_wd))
        )
        _data_to_create = []
        while _date <= end_day:
            if not self.env[self._name].search(
                [
                    ("target_date", ">=", _date),
                    ("target_date", "<=", _date + timedelta(days=6)),
                ]
            ):
                _data_to_create.append({"target_date": _date, "fold": True})
            _date += timedelta(days=7)
        if _data_to_create:
            records = self.env[self._name].get_or_create_from_target_date_multi(
                _data_to_create
            )
        res = {"type": "ir.actions.client", "tag": "reload"}
        return res

    @api.model
    def get_or_create_from_target_date_multi(self, datas):
        records = self.env[self._name]
        for data in datas:
            records += self.env[self._name].get_or_create_from_target_date(**data)
        return records

    @api.model
    def get_or_create_from_target_date(self, target_date: date, fold=False):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        _by = get_param("ntp_payable_management.payment_plan_by")
        _wd = get_param("ntp_payable_management.payment_plan_pay_date_of_week")
        _md = get_param("ntp_payable_management.payment_plan_pay_date_of_month") or 1
        plan_target_date = (
            target_date
            - timedelta(days=target_date.weekday())
            + timedelta(days=int(_wd))
        )
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        record = self.env[self._name].search(
            [("target_date", ">=", start_of_week), ("target_date", "<=", end_of_week)]
        )
        if not record:
            _data_to_create = {"target_date": plan_target_date, "fold": fold}
            record = self.env[self._name].create(_data_to_create)
        # auto create plan month related to plan week
        record_month = self.env[
            "account.payment.plan.month"
        ].get_or_create_from_target_date(target_date, fold)
        record.plan_month_id = record_month
        return record

    def auto_fold_today(self):
        self.env["account.payment.plan.week"].sudo().search([])._auto_fold_today("week")

    def auto_sort(self):
        self.env["account.payment.plan.week"].sudo().search([])._auto_sort("week")


class AccountPaymentPlan(models.Model):
    _name = "account.payment.plan.month"
    _inherit = "account.payment.plan.base"
    _description = "Account Payment Plans Month"

    payment_ids = fields.One2many("account.payment", "plan_month_id")
    plan_week_ids = fields.One2many("account.payment.plan.week", "plan_month_id")
    budget_in = fields.Monetary("Budget In", store=True, compute="_compute_budget")
    budget_out = fields.Monetary("Budget Out", store=True, compute="_compute_budget")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    def name_get(self):
        today = fields.Date.today()
        result = []
        # fmt: off
        for record in self:
            if record.target_date.year == today.year:
                diff = today.month - record.target_date.month
                if diff < 0:
                    diff = f'(+{abs(diff)})'
                elif diff > 0:
                    diff = f'(-{abs(diff)})'
                else:
                    diff = '(0)'
                result.append((record.id, "%s %s" % (record.name, diff)))
            else:
                result.append((record.id, "%s" % (record.name)))
        # fmt: on
        return result

    @api.depends("plan_week_ids.budget_out", "plan_week_ids.budget_in", "plan_week_ids")
    def _compute_budget(self):
        for rec in self:
            rec.budget_out = sum(
                [x.budget_out for x in self.plan_week_ids if x.budget_out]
            )
            rec.budget_in = sum(
                [x.budget_in for x in self.plan_week_ids if x.budget_in]
            )

    def button_recompute_budget(self):
        for rec in self:
            rec._compute_budget()

    @api.depends("target_date")
    def _compute_data(self):
        for rec in self:
            if rec.target_date:
                name = "{} - {}".format(
                    rec.target_date.year, rec.target_date.strftime("%b")
                )
                rec.name = name
                # sequence = year * 100 + week_no
                rec.sequence = (
                    rec.target_date.year * 100 + rec.target_date.isocalendar()[1]
                )
            else:
                rec.sequence = 1
                rec.name = f"Draft Plan Month"

    @api.model
    def get_or_create_from_target_date(self, target_date: date, fold=False):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        _by = get_param("ntp_payable_management.payment_plan_by")
        _wd = get_param("ntp_payable_management.payment_plan_pay_date_of_week")
        _md = get_param("ntp_payable_management.payment_plan_pay_date_of_month") or 1
        plan_target_date = (
            target_date - timedelta(days=target_date.day) + timedelta(days=int(_md))
        )
        start_of_month = target_date.replace(day=1)
        end_of_month = start_of_month + relativedelta(months=1, days=-1)
        record = self.env[self._name].search(
            [("target_date", ">=", start_of_month), ("target_date", "<=", end_of_month)]
        )
        if not record:
            _data_to_create = {"target_date": plan_target_date, "fold": fold}
            record = self.env[self._name].create(_data_to_create)
        return record

    def auto_fold_today(self):
        self.env["account.payment.plan.month"].sudo().search([])._auto_fold_today(
            "month"
        )

    def auto_sort(self):
        self.env["account.payment.plan.month"].sudo().search([])._auto_sort("month")
