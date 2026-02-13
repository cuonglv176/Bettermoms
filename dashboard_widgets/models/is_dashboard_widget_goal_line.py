from odoo import api, fields, models


class DashboardWidgetGoal(models.Model):
    _name = 'is.dashboard.widget.goal'
    _description = "Dashboard Goal Line"
    _rec_name = 'date'
    _order = 'date'

    date = fields.Date("Start Date", required=True)
    goal = fields.Float(string="Goal Value")
    dashboard_widget_1_id = fields.Many2one(string="Dashboard Item (1)", comodel_name='is.dashboard.widget')
    dashboard_widget_2_id = fields.Many2one(string="Dashboard Item (2)", comodel_name='is.dashboard.widget')
    dashboard_widget_id_type = fields.Selection(string='Type', compute='_compute_dashboard_widget_id_type', selection=lambda self: self.env['is.dashboard.widget']._fields['widget_type'].selection)

    user_id = fields.Many2one('res.users')  # Show as first field in FV's LV
    custom_filter_data = fields.Char()

    @api.depends('dashboard_widget_1_id.widget_type', 'dashboard_widget_2_id.widget_type')
    def _compute_dashboard_widget_id_type(self):
        for rec in self:
            widget = rec.dashboard_widget_1_id or rec.dashboard_widget_2_id
            rec.dashboard_widget_id_type = widget.widget_type


class FakeGoalLine(object):
    date = False
    goal = 0
    custom_filter_data = False
    user_id = False
