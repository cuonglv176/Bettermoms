from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval as safe_eval
from datetime import datetime, date


class DashboardWidgetNotes(models.Model):
    _inherit = 'is.dashboard.widget'

    note = fields.Text(string="Internal Notes")
    note_kanban = fields.Html(string="Notes On Dashboard")
    display_note_kanban = fields.Html(string="Notes On Dashboard", compute="_compute_display_note_kanban")

    def _compute_display_note_kanban(self):
        """
        Render the notes as a mail template so we can insert values from the context
        :return:
        """
        for rec in self:
            # Get the context of the parameter data
            rec.display_note_kanban = rec._render_content_as_template(rec.note_kanban)
