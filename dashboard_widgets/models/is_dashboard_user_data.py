from odoo import api, fields, models
import json


class IsDashboardUserData(models.Model):
    _name = 'is.dashboard.user_data'
    _description = "Dashboard User Data"

    dashboard_id = fields.Many2one('is.dashboard')
    user_id = fields.Many2one('res.users')

    date_range_type = fields.Char()
    parameter_data = fields.Text(default="{}")

    def get_param_data(self, key=None):
        data = json.loads(self.parameter_data or "{}")
        if key:
            return data.get(key)
        return data

    def update_param_data(self, update_dict):
        data = self.get_param_data()
        data.update(update_dict)
        self.parameter_data = json.dumps(data)
