from odoo import models, fields, api

from datetime import datetime, date, time, timedelta
from odoo.tools.safe_eval import safe_eval as safe_eval
import json
from .is_dashboard_widget_goal_line import FakeGoalLine

IS_ODOO_VERSION_BEFORE_v12 = False


class DashboardWidgetGoal(models.Model):
    _inherit = 'is.dashboard.widget'

    # TODO: Is anyone using goal_total?
    goal_count = fields.Float(string="Standard Goal (1)")
    goal_total = fields.Float(string="Standard Goal (2)")

    goal_1_show_future_goals = fields.Boolean("Show future goals (Limited/Experimental feature)")
    goal_1_is_greater_than = fields.Boolean(string="Goal is greater than (1)", default=True)
    goal_1_line_ids = fields.One2many(comodel_name="is.dashboard.widget.goal", inverse_name="dashboard_widget_1_id")
    goal_2_is_greater_than = fields.Boolean(string="Goal is greater than (2)", default=False)
    goal_2_line_ids = fields.One2many(comodel_name="is.dashboard.widget.goal", inverse_name="dashboard_widget_2_id")

    current_goal_date_start = fields.Date(string="Goal Start", compute='compute_current_goal_count')
    current_goal_date_end = fields.Date(string="Goal End", compute='compute_current_goal_count')

    force_show_goal_tabs = fields.Boolean(string="Advanced Python Goals", compute="_compute_force_show_goal_tabs", inverse="_inverse_force_show_goal_tabs")
    show_python_custom_goal1_filter = fields.Boolean("Show Advanced Filtering (1)")
    show_python_custom_goal2_filter = fields.Boolean("Show Advanced Filtering (2)")
    python_custom_goal1 = fields.Char("Python Custom Goal (1)")
    python_custom_goal1_filter = fields.Char("Python Custom Goal Filter (1)")
    python_custom_goal2 = fields.Char("Python Custom Goal (2)")
    python_custom_goal2_filter = fields.Char("Python Custom Goal Filter (2)")

    def get_run_python_count_eval_context_goal_lines(self,goal_lines):
        dict = self.get_run_python_count_eval_context()
        dict['goal_lines'] = goal_lines
        dict['eval'] = eval
        return dict

    def filter_goal_lines(self, goal_lines, code, lambda_filter=None, lambda_filter_data=None):
        if not goal_lines:
            return goal_lines
        if lambda_filter:
            goal_lines = goal_lines.filtered(lambda goal: lambda_filter(goal, lambda_filter_data))
        if not code:
            return goal_lines.filtered(lambda a: self.env.user == a.user_id or not a.user_id)

        eval_context = self.get_run_python_count_eval_context_goal_lines(goal_lines)
        try:
            goal_lines = safe_eval(code, eval_context, mode="eval", nocopy=True)
        except Exception as ex:
            return False
        return goal_lines

    def get_1_goal_for_date(self, start_date, end_date, current_goal_value_only=False, lambda_filter=False, lambda_filter_data=None):
        if self.python_custom_goal1:
            eval_context = self.get_run_python_count_eval_context_goal_lines(self.goal_1_line_ids)
            eval_context['start_datetime'] = start_date
            eval_context['end_datetime'] = end_date
            locals = {}
            try:
                safe_eval(self.python_custom_goal1, eval_context, locals, mode="exec", nocopy=True)
            except Exception as ex:
                self._add_render_dashboard_markup_error('run_python_count', ex)
                return False, False, 0

            if current_goal_value_only:
                return locals.get('goal', 0)
            else:
                default_current_goal = FakeGoalLine()
                default_current_goal.date = start_date
                default_current_goal.goal = locals.get('goal', 0),
                return locals.get('current_goal_line', default_current_goal), locals.get('next_goal_line', False), locals.get('goal', 0)


        filtered_goal_lines = self.filter_goal_lines(self.goal_1_line_ids, self.python_custom_goal1_filter, lambda_filter=lambda_filter, lambda_filter_data=lambda_filter_data)
        if not filtered_goal_lines:
            value = self._prorata_goal_date(
                self.goal_count,
                self.query_1_config_datetime_range_start,
                datetime.today(),
                self.query_1_config_datetime_range_end,
            )
            if current_goal_value_only:
                return value
            else:
                return False, False, value

        return self._get_goal_for_date(
            filtered_goal_lines,
            self.python_custom_goal1_filter,
            self.goal_count,
            start_date,
            end_date,
            current_goal_value_only=current_goal_value_only,
        )

    def get_2_goal_for_date(self, start_date, end_date, current_goal_value_only=False, lambda_filter=False, lambda_filter_data=None):
        if self.python_custom_goal2:
            eval_context = self.get_run_python_count_eval_context_goal_lines(self.goal_2_line_ids)
            eval_context['start_datetime'] = start_date
            eval_context['end_datetime'] = end_date
            locals = {}
            try:
                safe_eval(self.python_custom_goal2, eval_context, locals, mode="exec", nocopy=True)
            except Exception as ex:
                self._add_render_dashboard_markup_error('run_python_count', ex)
                return False, False, 0

            if current_goal_value_only:
                return locals.get('goal', 0)
            else:
                default_current_goal = self.env['is.dashboard.widget.goal'].new({
                    'date': start_date,
                    'goal': locals.get('goal', 0),
                })
                return locals.get('current_goal_line', default_current_goal), locals.get('next_goal_line', False), locals.get('goal', 0)


        filtered_goal_lines = self.filter_goal_lines(self.goal_2_line_ids, self.python_custom_goal2_filter, lambda_filter=lambda_filter, lambda_filter_data=lambda_filter_data)
        if not filtered_goal_lines:
            value = self._prorata_goal_date(
                self.goal_total,
                self.query_2_config_datetime_range_start,
                datetime.today(),
                self.query_2_config_datetime_range_end,
            )
            if current_goal_value_only:
                return value
            else:
                return False, False, value

        return self._get_goal_for_date(
            filtered_goal_lines,
            self.python_custom_goal2_filter,
            self.goal_total,
            start_date,
            end_date,
            current_goal_value_only=current_goal_value_only,
        )

    def _prorata_goal_date(self, goal_value, start_date, current_date, end_date):
        business_days_done = self.get_working_days(start_date, current_date)
        business_days_total = self.get_working_days(start_date, end_date)
        business_days_percent = business_days_done / business_days_total if business_days_total else 0
        return goal_value * business_days_percent

    def _prorata_goal_start(self, goal, previous_goal, current_date):
        business_days_done = self.get_working_days(current_date, goal.date)
        business_days_total = self.get_working_days(previous_goal.date, goal.date)
        business_days_percent = business_days_done / business_days_total if business_days_total else 0
        return previous_goal.goal * business_days_percent if goal else 0

    def _prorata_goal_end(self, goal, next_goal, current_date):
        business_days_done = self.get_working_days(goal.date, current_date)
        business_days_total = self.get_working_days(goal.date, next_goal.date - timedelta(days=1))
        business_days_percent = business_days_done / business_days_total if business_days_total else 0
        return goal.goal * business_days_percent if goal else 0

    def _get_goal_for_date(self, lines, python_custom_goal_filter, default_goal, start_date, current_date, current_goal_value_only=False):
        if not start_date or not current_date:

            # If there is no end/current date then do no prorata and just use the goal value. Eg. it would be a monthly goal for each month until the next value
            current_goals = self.filter_goal_lines(lines, python_custom_goal_filter).sorted(key='date', reverse=True)
            if start_date:
                _start_date = self._convert_string_date_or_datetime_to_date_if_not_already(start_date)
                current_goals = current_goals.filtered(lambda b: b.date and fields.Date.from_string(b.date) <= _start_date)
            if current_goals:
                if current_goal_value_only:
                    return current_goals[0].goal
                else:
                    return current_goals[0], False, current_goals[0].goal
            return False, False, 0
        try:
            if not isinstance(current_date, date):
                # TODO: Do we need to do anything with TZ here?
                current_date = fields.Date.from_string(current_date)

            current_goals = lines.filtered(lambda b: b.date and fields.Date.from_string(b.date) < current_date).sorted(key='date', reverse=True)

            if start_date:
                current_goals = current_goals.filtered(lambda b: b.date and fields.Date.from_string(b.date) >= start_date).sorted(key='date', reverse=True)

            current_goal = current_goals[0] if current_goals else False

            if current_goal_value_only:
                return current_goal.goal if current_goal else default_goal

            if current_goal:
                next_goal = lines.filtered(lambda b: b.date and fields.Date.from_string(b.date) > fields.Date.from_string(current_goal.date)).sorted(key='date')
                next_goal = next_goal[0] if next_goal else False
            else:
                next_goal = False

            if len(current_goals) > 1:
                total_goal_value = 0
                previous_goal = lines.filtered(lambda b: b.date and fields.Date.from_string(b.date) < fields.Date.from_string(current_goal.date)).sorted(key='date')
                previous_goal = previous_goal[0] if next_goal else False
                if start_date and current_goals[-1].date > start_date:
                    # Prorata previous goal for the part that applies inside the start date
                    total_goal_value += self._prorata_goal_start(current_goals[-1], previous_goal, start_date)
                else:
                    total_goal_value += current_goals[-1].goal
                total_goal_value += sum(current_goals.mapped('goal')[1:-1])
                total_goal_value += self._prorata_goal_end(current_goals[0], next_goal, current_date)
            else:
                total_goal_value = current_goal.goal if current_goal else default_goal

            return current_goal, next_goal, total_goal_value
        except Exception as ex:
            return False, False, 0

    def _convert_string_date_or_datetime_to_date_if_not_already(self, value):
        if not isinstance(value, date) and not isinstance(value, datetime):
            if value and '' in value:
                return fields.Datetime.context_timestamp(self, fields.Datetime.from_string(value)).date()
            else:
                return fields.Date.from_string(value)
        else:
            return value

    def _convert_datetime_to_local_date_string(self, value):
        if not value:
            return value
        if not isinstance(value, date) and not isinstance(value, datetime):
            value = fields.Datetime.from_string(value)
        return fields.Datetime.context_timestamp(self, value).date()

    @api.depends(
        'goal_1_line_ids',
        'goal_1_line_ids.date',
        'goal_1_line_ids.goal',
        # 'query_1_config_datetime_range_start',
        # 'query_1_config_date_range_start',
        # 'query_1_config_date_is_datetime',
    )
    def compute_current_goal_count(self):
        for rec in self:
            try:
                is_datetime, start, end, error = rec.get_query_1_config_date_range(allow_return_as_string_pre_v12=False)
                if error:
                    rec._add_render_dashboard_markup_error('compute_current_goal_count', error)

                start_date = self._convert_datetime_to_local_date_string(start) if is_datetime else start
                end_date = self._convert_datetime_to_local_date_string(end) if is_datetime else end
                current_goal, next_goal, total_goal_value = rec.get_1_goal_for_date(start_date, end_date)

                rec.current_goal_count = total_goal_value if current_goal else rec.goal_count
                # TODO migrate to use the goal_2_line_ids rec.current_goal_total = current_goal.goal_total if current_goal else rec.goal_count

                rec.current_goal_date_start = current_goal.date if current_goal else False
                rec.current_goal_date_end = next_goal.date if next_goal else False
            except Exception as ex:
                rec.current_goal_count = 0
                rec.current_goal_date_start = False
                rec.current_goal_date_end = False

    @api.depends(
        'goal_2_line_ids',
        'goal_2_line_ids.date',
        'goal_2_line_ids.goal',
        # 'query_2_config_datetime_range_start',
        # 'query_2_config_date_range_start',
        # 'query_2_config_date_is_datetime',
    )
    def compute_current_goal_total(self):
        for rec in self:
            try:
                start_date = rec._convert_datetime_to_local_date_string(rec.query_2_config_datetime_range_start) if rec.query_2_config_date_is_datetime else rec.query_2_config_date_range_start
                end_date = rec._convert_datetime_to_local_date_string(rec.query_2_config_datetime_range_end) if rec.query_2_config_date_is_datetime else rec.query_2_config_date_range_end
                current_goal, next_goal, total_goal_value = rec.get_2_goal_for_date(start_date, end_date)

                rec.current_goal_total = total_goal_value if current_goal else rec.goal_total

                # rec.current_goal_date_start = current_goal.date if current_goal else False
                # rec.current_goal_date_end = next_goal.date if next_goal else False
            except:
                rec.current_goal_total = 0

    @api.depends('show_python_custom_goal1_filter', 'show_python_custom_goal2_filter')
    def _compute_force_show_goal_tabs(self):
        for rec in self:
            rec.force_show_goal_tabs = rec.show_python_custom_goal1_filter or rec.show_python_custom_goal2_filter

    def _inverse_force_show_goal_tabs(self):
        for rec in self:
            rec.update({
                'show_python_custom_goal1_filter': rec.force_show_goal_tabs,
                'show_python_custom_goal2_filter': rec.force_show_goal_tabs,
            })

    @api.onchange('force_show_goal_tabs')
    def _onchange_force_show_goal_tabs(self):
        self._inverse_force_show_goal_tabs()
