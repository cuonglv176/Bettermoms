from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval as safe_eval

import datetime
import dateutil
from dateutil import relativedelta

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class IsDashboardWidgetTableColumn(models.Model):
    _name = 'is.dashboard.widget.record_list.column'
    _description = 'Dashboard record list field'
    _order = 'sequence'

    sequence = fields.Integer()
    name = fields.Char(string="Label", required=True)
    type = fields.Selection(string="Type", selection=[
        ('field', 'Field'),
        ('related', 'Related Field'),
        ('python', 'Python Code (Advanced)'),
    ], default='field')

    field_id = fields.Many2one('ir.model.fields', string="Column")
    related_field_path = fields.Char()
    python_code = fields.Text()

    dashboard_id = fields.Many2one('is.dashboard.widget')
    column_class = fields.Char()
    format_string = fields.Char(string="Display Format", help="Python format string eg. '${:.2f}' OR strftime format string eg. '%d/%m/%Y'")

    @api.onchange('field_id')
    def onchange_name(self):
        for rec in self:
            rec.name = rec.field_id.field_description or rec.field_id.field_description

    def get_value(self, record, override_function=None, additional_data=None):
        if callable(override_function):
            res = override_function(record, self.field_id.name, self, additional_data)
            if res is not False:  # Allow 'None', etc to be a value if needed
                return res

        if self.type == 'field':
            value = record[self.field_id.name]
            if isinstance(value, models.Model) and len(value) > 1:
                return ', '.join(self._get_value(v) for v in value)
            else:
                return self._get_value(value)
        elif self.type == 'related':
            value = record.mapped(self.related_field_path)
            if isinstance(value, models.Model) and len(value) > 1:
                return ', '.join(self._get_value(v) for v in value)
            else:
                return self._get_value(value)
        elif self.type == 'python':
            value = self.get_python_value(record)
            if isinstance(value, models.Model) and len(value) > 1:
                return ', '.join(self._get_value(v) for v in value)
            else:
                return self._get_value(value)

        # python_get_column_value(record, self.record_list_column_ids[icolumn].field_id.name, column_record=self.record_list_column_ids[icolumn]) if callable(python_get_column_value)

    def _get_value(self, value):
        if isinstance(value, list):
            if len(value) == 0:
                return ''
            elif len(value) == 1:
                value = value[0]

        if hasattr(value, 'display_name'):
            value = value.display_name
        elif hasattr(value, 'name'):
            value = value.name
        if self.format_string:
            if isinstance(value, datetime.datetime):
                value = fields.Datetime.from_string(value).strftime(self.format_string) if value else ''
            elif isinstance(value, datetime.date):
                value = fields.Date.from_string(value).strftime(self.format_string) if value else ''
            else:
                value = self.format_string.format(value) if value else ''
        return value

    def get_python_value(self, record):
        locals = {}
        eval_context = self.get_run_python_count_eval_context(record)
        if self.python_code:
            try:
                return safe_eval(self.python_code, eval_context, locals, mode="eval", nocopy=True)
            except Exception as ex:
                return repr(ex)

    def get_run_python_count_eval_context(self, record):
        def _helper_max(seq):
            if not seq:
                return False
            return max(seq)

        res = self.dashboard_id.get_run_python_count_eval_context()
        res['record'] = record
        res['column'] = self
        res['max'] = _helper_max
        return res


class DashboardWidgetRecordList(models.Model):
    _inherit = 'is.dashboard.widget'

    display_mode = fields.Selection(selection_add=[
        ('record_list', 'Record List'),
    ], ondelete={'record_list': 'set default'})

    record_list_column_ids = fields.One2many(string="Record List Columns", comodel_name='is.dashboard.widget.record_list.column', inverse_name='dashboard_id')

    def copy(self, default=None):
        res = super(DashboardWidgetRecordList, self).copy(default=default)
        res.filtered(lambda d: d.drilldown_type == 'custom_action').action_update_auto_view()
        return res

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'goal_1_line_ids' not in default:
            default['goal_1_line_ids'] = [(0, 0, line.copy_data()[0]) for line in self.goal_1_line_ids]
        if 'goal_2_line_ids' not in default:
            default['goal_2_line_ids'] = [(0, 0, line.copy_data()[0]) for line in self.goal_2_line_ids]
        if 'record_list_column_ids' not in default:
            default['record_list_column_ids'] = [(0, 0, line.copy_data()[0]) for line in self.record_list_column_ids]
        if 'query_1_config_domain_additional_ids' not in default:
            default['query_1_config_domain_additional_ids'] = [(0, 0, line.copy_data()[0]) for line in self.query_1_config_domain_additional_ids]
        if 'query_2_config_domain_additional_ids' not in default:
            default['query_2_config_domain_additional_ids'] = [(0, 0, line.copy_data()[0]) for line in self.query_2_config_domain_additional_ids]
        if 'open_action_1_auto_generate_view_column_ids' not in default:
            default['open_action_1_auto_generate_view_column_ids'] = [(0, 0, line.copy_data()[0]) for line in self.open_action_1_auto_generate_view_column_ids]
        return super(DashboardWidgetRecordList, self).copy_data(default)

    def _get_record_display_name(self, record):
        # TODO: Use Odoo standard function to get this from rec_name, etc.
        if hasattr(record, 'display_name'):
            return record.display_name
        elif hasattr(record, 'name'):
            return record.name
        return "{}".format(record)

    def get_render_data(self):
        render_data = super(DashboardWidgetRecordList, self).get_render_data()

        if self.display_mode != 'record_list':
            return render_data

        if not self.query_1_config_model_id:
            render_data['error'] = "Please set a record type by editing this dashboard item"
            return render_data
        python_get_column_value, python_additional_data = False, {}
        if self.datasource == 'python':
            python_data = self.eval_data(self.query_1_config_python, mode='exec') or {}
            records = python_data.get('records', self.env[self.query_1_config_model_id.model])
            python_get_column_value = python_data.get('record_list_get_column_value_func')
            python_additional_data = python_data.get('additional_data') or {}
        else:
            records = self.get_query_result(
                self.query_1_config_model_id,
                self.get_query_1_domain(),
                self.get_group_by_tuple(False, self.query_1_config_measure_operator, date_only_aggregate=False),  # Do not use a measure on record list query (self.query_1_config_measure_field_id)
                orderby="{} {}".format(self.chart_1_config_sort_field_id.name, "DESC" if self.chart_1_config_sort_descending else "ASC") if self.chart_1_config_sort_field_id else "",
                limit=self.query_1_config_result_limit or 100,
                sudo=self.query_1_sudo,
                return_record_set=True,
            )

        headers = [{
            'name': column.name,
        } for column in self.record_list_column_ids]

        render_data['table'] = {
            'record': self,
            'headers': headers,
            'rows': [[{
                'value': self.record_list_column_ids[icolumn].get_value(record, override_function=python_get_column_value, additional_data=python_additional_data),
                'display_value': self.record_list_column_ids[icolumn].get_value(record, override_function=python_get_column_value, additional_data=python_additional_data),
                'class': column.column_class or '',
                'action': {
                    'type': 'object',
                    'name': 'action_table_action',
                    'class': 'oe_kanban_action',
                    'context': {
                        'action_model': self.query_1_config_model_id.model,
                        'action_domain': [('id', 'in', records.ids)],
                        'action_name': self._get_record_display_name(record),
                        'open_form_view_res_id': record.id,
                        'dashboard_widget_id': self.id,
                    }
                },
            } for icolumn, column in enumerate(self.record_list_column_ids)] for record in records],
        }

        return render_data
