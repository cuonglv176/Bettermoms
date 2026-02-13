# __author__ = 'BinhTT'
from odoo import fields, models
from datetime import date

class DocumentFolder(models.Model):
    _inherit = 'documents.folder'

    ir_model = fields.Many2one('ir.model', string='Model')
