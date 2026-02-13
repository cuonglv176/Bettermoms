from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval as safe_eval

from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
from dateutil import rrule
import pytz

IS_ODOO_VERSION_BEFORE_v12 = True


class DashboardDatasourceSql(models.Model):
    _inherit = 'is.dashboard.widget'

    datasource = fields.Selection(default="query", selection_add=[('sql', "SQL Query (Advanced)")], ondelete={'sql': 'set default'})

    query_1_config_sql = fields.Text()
    query_2_config_sql = fields.Text()

    def run_sql_count(self):
        if self.query_1_config_sql:
            self.env.cr.execute(self.query_1_config_sql)
            results = self.env.cr.dictfetchall()
            if results:
                self.count = results[0].get('count')
                self.total = results[0].get('total')
                return

        self.count = 0
        self.total = 0

    def chart_get_data_query_sql_1(self):
        return self.chart_get_data_query_sql(
            self.query_1_config_model_id,
            self.query_1_config_sql,
            self.chart_1_config_color,
            self.chart_1_config_area,
            self.chart_1_config_title,
        )

    def chart_get_data_query_sql_2(self):
        return self.chart_get_data_query_sql(
            self.query_2_config_model_id,
            self.query_2_config_sql,
            self.chart_2_config_color,
            self.chart_2_config_area,
            self.chart_2_config_title,
        )

    def chart_get_data_query_sql(self, model, sql, chart_config_color, chart_config_area, chart_config_title):
        date_start = []

        if sql:
            try:
                self.env.cr.execute(sql)
                results = self.env.cr.fetchall()
            except:
                return {
                   'labels': [],
                   'dates': [],
                   'datasets': [],
                }, chart_config_color, chart_config_area, chart_config_title

            if results:
                columns = list(map(lambda c: c.name, self.env.cr._obj.description))
                labels = list(map(lambda r: r[0], results))

                datasets = []
                for iCol in range(1, len(columns)):
                    domains = []
                    datasets.append({
                        'label': columns[iCol],
                        'data': list(map(lambda row: row[iCol] or False, results)),
                        'domains': list(domains),
                        'date_start': list(date_start) if date_start else [],
                        # 'action_id': action.id,
                        'model': model.model,
                        'query_name': columns[iCol],
                    })

                return {
                    'labels': labels,
                    'dates': list(date_start) if date_start else [],
                    'datasets': datasets,
                }, chart_config_color, chart_config_area, chart_config_title

        return {
                   'labels': [],
                   'dates': [],
                   'datasets': [],
               }, chart_config_color, chart_config_area, chart_config_title
