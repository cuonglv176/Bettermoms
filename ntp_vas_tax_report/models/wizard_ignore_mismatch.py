# __author__ = 'BinhTT'
from odoo import models, fields

class WizardIgnoreMismatch(models.Model):
    _name = "wizard.ignore.mismatch"

    reason_ignore_mismatch = fields.Char(string="Reason Ignore Mismatch")

    def action_ignore_mismatch(self):
        ctx = self.env.context.copy()
        move_line_ids = self.env['account.move.line'].browse(ctx.get('move_line_ids'))
        move_line_ids.sudo().write({'ignore_mismatch': True, 'reason_ignore_mismatch': self.reason_ignore_mismatch})
        return