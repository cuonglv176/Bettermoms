from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval as safe_eval
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import datetime
import dateutil
from dateutil import relativedelta
import babel.dates


class IsDashboardParameter(models.Model):
    _name = 'is.dashboard.parameter'
    _description = 'Dashboard Parameter'
    _order = "sequence,id"

    sequence = fields.Integer()
    dashboard_id = fields.Many2one(comodel_name='is.dashboard', string='Dashboard')
    name = fields.Char(string="Name", required=True)
    parameter_type = fields.Selection(selection=[
        ('char', 'Text'),
        # ('date', 'Date'),
        # ('datetime', 'Datetime'),
        ('integer', 'Integer (Whole number)'),
        ('float', 'Float (Decimal number)'),
        ('one2many', 'One2many (Record)'),
        ('eval', 'Python (Advanced)'),
    ], required=True, default='char')
    value_char = fields.Char(string="Value (Text)")
    value_date = fields.Date(string="Value (Date)")
    value_datetime = fields.Datetime(string="Value (Datetime)")
    value_integer = fields.Integer(string="Value (Integer)")
    value_float = fields.Float(string="Value (Float)")
    value_reference = fields.Reference(string="Value (Datetime)", selection='_selection_model',)
    value_eval = fields.Text(string="Value (Eval)")
    value_display = fields.Char(compute="compute_value_display")
    user_editable = fields.Boolean()

    help_message = fields.Html(compute="compute_help_message")

    def get_parameter_value(self, user_data=False, json_compatible=False):
        if self.user_editable and user_data:
            value = user_data.get_param_data(self.name)
            if value:
                if self.parameter_type == "one2many":
                    return self.value_reference.browse(value).exists()
                else:
                    return value

        if self.parameter_type == 'char':
            return self.value_char or None
        elif self.parameter_type == 'date':
            if json_compatible and self.value_date:
                return "TODO: date json"
            return self.value_date
        elif self.parameter_type == 'datetime':
            if json_compatible and self.value_datetime:
                return "TODO: datetime json"
            return self.value_datetime
        elif self.parameter_type == 'integer':
            return self.value_integer
        elif self.parameter_type == 'float':
            return self.value_float
        elif self.parameter_type == 'one2many':
            if json_compatible and self.value_reference:
                return self.value_reference.id
            return self.value_reference
        elif self.parameter_type == 'eval':
            data = self.eval_data(self.value_eval, mode='exec')
            if data and 'value' in data:
                return data['value']
            return False
        else:
            return False

    def get_run_python_count_eval_context(self):
        return {
            'dashboard': self.dashboard_id,
            'env': self.env,
            'user': self.env.user,
            'uid': self.env.user.id,
            'datetime': datetime,
            'dateutil': dateutil,
            'relativedelta': relativedelta.relativedelta,
            'context_today': lambda: fields.Date.context_today(self),
            'format_date': babel.dates.format_datetime,

            'ref': self.env.ref,
            'context': self.env.context,

            'DEFAULT_SERVER_DATE_FORMAT': DEFAULT_SERVER_DATE_FORMAT,
            'DEFAULT_SERVER_DATETIME_FORMAT': DEFAULT_SERVER_DATETIME_FORMAT,
        }

    def eval_data(self, code, mode='eval'):
        locals = {}
        eval_context = self.get_run_python_count_eval_context()
        if code:
            try:
                res = safe_eval(code, eval_context, locals, mode=mode, nocopy=True)
                return locals if mode == 'exec' else res
            except Exception as ex:
                return False

    @api.depends(
        'parameter_type',
        'value_char',
        'value_date',
        'value_datetime',
        'value_integer',
        'value_float',
        'value_reference',
    )
    @api.onchange(
        'parameter_type',
        'value_char',
        'value_date',
        'value_datetime',
        'value_integer',
        'value_float',
        'value_reference',
    )
    def compute_value_display(self):
        for rec in self:
            val = rec.get_parameter_value()
            if rec.parameter_type == 'one2many' and val:
                val = "{}: {}".format(val._description, val[val._rec_name])
            rec.value_display = val

    @api.model
    def _selection_model(self):
        return [
            (x, _(self.env[x]._description)) for x in self.env
        ]

    @api.depends(
        'parameter_type',
        'name',
    )
    @api.onchange(
        'parameter_type',
        'name',
    )
    def compute_help_message(self):
        for rec in self:
            message = """
            In a dashboard tile untick "Use Domain Editor" and then you can add this parameter '{param_name}' to the domain.<br />
            <br />
            eg. [('field', '=', params.get('{param_name}'))]<br />
            <br />
            """.format(
                param_name=rec.name,
            )
            if rec.parameter_type == 'one2many':
                message += """
                Note: for a record type you will want to add ".id" to the end eg. params.get('{param_name}').id<br />
                """.format(
                    param_name=rec.name,
                )

            user_editable_supported_types = [
                'one2many',
                'char',
                'float',
                'integer',
            ]
            if rec.user_editable and rec.parameter_type not in user_editable_supported_types:
                message += """
                <strong>Note: User editable parameters currently only supported for the following parameter types:
                <ul>{}</ul></strong></strong><br />
                """.format(
                    ''.join("<li>{}</li>".format(t) for t in user_editable_supported_types),
                    param_name=rec.name,
                )
            rec.help_message = message
