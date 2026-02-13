from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval as safe_eval
from odoo import tools


import datetime
import dateutil
from dateutil import relativedelta
import babel.dates

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

IS_ODOO_VERSION_BEFORE_v12 = False


class DashboardWidget(models.Model):
    _inherit = 'is.dashboard.widget'

    datasource = fields.Selection(selection_add=[
        ('python', 'Python (Advanced)'),
    ], ondelete={'python': 'set default'})

    query_1_config_python_domain = fields.Text(compute="compute_python_dom")
    query_2_config_python_domain = fields.Text(compute="compute_python_dom")

    query_1_table = fields.Text(compute="compute_python_dom")

    query_1_config_python = fields.Text("Python Code")

    def get_run_python_count_eval_context(self):

        dashboard = self.env['is.dashboard'].browse(self.env.context['dashboard_id']) if self.env.context.get('dashboard_id') else self.env['is.dashboard']
        user_data = dashboard.get_or_create_user_dashboard_data()
        return {
            'dashboard': self,

            'model': self.query_1_config_model_id.model,
            'date_range_start': self.query_1_config_date_range_start or self.query_1_config_datetime_range_start,
            'date_range_end': self.query_1_config_date_range_end or self.query_1_config_datetime_range_end,

            'dom1': self.query_1_config_python_domain,
            'dom2': self.query_2_config_python_domain,
            'get_query_domain_1': self.get_query_1_domain,
            'get_query_domain_2': self.get_query_2_domain,

            'env': self.env,
            'user': self.env.user,
            'uid': self.env.user.id,
            'datetime': tools.safe_eval.datetime,
            'dateutil': tools.safe_eval.dateutil,
            'relativedelta': relativedelta.relativedelta,
            'context_today': lambda: fields.Date.context_today(self),
            'format_date': babel.dates.format_datetime,

            'get_date_range': self.python_get_date_range,
            'get_date_range_query_1': self.python_get_date_range_query_1,
            'get_date_range_query_2': self.python_get_date_range_query_2,
            'get_custom_goal_1': self.get_custom_goal_1,
            'get_custom_goal_2': self.get_custom_goal_2,
            'ref': self.env.ref,
            'context': self.env.context,
            'params': dashboard.get_parameter_dict(user_data=user_data),

            'DEFAULT_SERVER_DATE_FORMAT': DEFAULT_SERVER_DATE_FORMAT,
            'DEFAULT_SERVER_DATETIME_FORMAT': DEFAULT_SERVER_DATETIME_FORMAT,
        }

    def get_custom_goal_1(self, target_value, custom_data_separator=':', default=0, user_id=None):
        return self.get_custom_goal(self.goal_1_line_ids, target_value, custom_data_separator=custom_data_separator, default=default, user_id=user_id)

    def get_custom_goal_2(self, target_value, custom_data_separator=':', default=0, user_id=None):
        return self.get_custom_goal(self.goal_2_line_ids, target_value, custom_data_separator=custom_data_separator, default=default, user_id=user_id)

    def get_custom_goal(self, goals, target_value, custom_data_separator=':', default=0, user_id=None):
        if target_value:
            if custom_data_separator:
                goals = goals.filtered(lambda g: int(g.custom_filter_data.split(custom_data_separator)[0]) == target_value)
            else:
                goals = goals.filtered(lambda g: g.custom_filter_data == target_value)

        if user_id:
            goals = goals.filtered(lambda g: g.user_id.id == user_id)

        if goals:
            return goals[0].goal
        else:
            return default

    def compute_python_dom(self):
        for rec in self:
            rec.run_python_count()

    def run_python_count(self):
        code = self.query_1_config_python
        locals = {}
        eval_context = self.get_run_python_count_eval_context()
        if code:
            try:
                safe_eval(code, eval_context, locals, mode="exec", nocopy=True)
            except Exception as ex:
                self._add_render_dashboard_markup_error('run_python_count', ex)

            self.count = locals.get('count', 0)
            self.total = locals.get('total', 0)

            if 'goal_count' in locals:
                self.current_goal_count = locals.get('goal_count', 0)

            self.query_1_config_python_domain = locals.get('dom1', False)
            self.query_2_config_python_domain = locals.get('dom2', False)
            self.query_1_table = locals.get('table', False)
        else:
            self.count = 0
            self.total = 0

    def eval_data(self, code, mode='eval'):
        locals = {}
        eval_context = self.get_run_python_count_eval_context()
        if code:
            try:
                res = safe_eval(code, eval_context, locals, mode=mode, nocopy=True)
                return locals if mode == 'exec' else res
            except Exception as ex:
                return False
