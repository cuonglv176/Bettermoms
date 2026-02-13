from odoo import api, fields, models
from odoo.addons.web.controllers.main import clean_action


class DashboardWizardCreate(models.TransientModel):
    _name = 'is.dashboard.widget.wizard.create'
    _description = 'Dashboard Create Wizard'

    name = fields.Char(string="Name", required=True)
    menu_id = fields.Many2one(comodel_name='ir.ui.menu', string="Parent Menu")
    group_ids = fields.Many2many(comodel_name='res.groups', string="Allowed Groups", relation="is_dashboard_widget_wizard_create_res_groups_rel")

    duplicate_dashboard_id = fields.Many2one(comodel_name='is.dashboard', string="Duplicate Dashboard")

    def action_create(self):
        dashboard = self.env['is.dashboard'].create({'menu_id': self.menu_id.id, 'name': self.name, 'group_ids': self.group_ids.ids})
        action = dashboard.menu_id.action.read([])[0]
        action = clean_action(action, self.env)
        return action

    def _action_duplicate(self, as_link=False, return_action=False):
        dashboard = self.env['is.dashboard'].create({'menu_id': self.menu_id.id, 'name': self.name, 'group_ids': self.group_ids.ids})
        for template_widget in self.duplicate_dashboard_id.with_context(dashboard_id=self.duplicate_dashboard_id.id).widget_ids:
            if as_link:
                widget = template_widget
            else:
                widget = template_widget.copy()

            dashboard.add_widget(dashboard.id, widget.id, default_size_auto=True)
            widget = widget.with_context(dashboard_id=dashboard.id)
            widget.pos_x = template_widget.pos_x
            widget.pos_y = template_widget.pos_y
            widget.size_x = template_widget.size_x
            widget.size_y = template_widget.size_y

        if return_action:
            action = dashboard.menu_id.action.read([])[0]
            action = clean_action(action, self.env)
            return action

    def action_duplicate_link(self):
        return self._action_duplicate(as_link=True, return_action=True)

    def action_duplicate_copy(self):
        return self._action_duplicate(as_link=False, return_action=True)
