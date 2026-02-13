# -*- coding: utf-8 -*-

from odoo import fields, models, api


class AccountJournal(models.Model):
    _inherit = "account.journal"

    pc_sequence_id = fields.Many2one('ir.sequence', string='Số Phiếu Chi', help="Số PC liên quan đến sổ nhật ký này.",
                                     copy=False)
    pc_code = fields.Char(string='Tiền Tố Phiếu Chi', related='pc_sequence_id.prefix')
    pt_sequence_id = fields.Many2one('ir.sequence', string='Số Phiếu Thu', help="Số PT liên quan đến sổ nhật ký này.",
                                     copy=False)
    pt_code = fields.Char(string='Tiền Tố Phiếu Thu', related="pt_sequence_id.prefix")
    manager_id = fields.Many2one("res.users", string="Tổng giám đốc",
                                 default=lambda self: self.env.user.company_id.manager.id)
    accountant_id = fields.Many2one("res.users", string="Kế toán trưởng",
                                    default=lambda self: self.env.user.company_id.accountant.id)
    treasurer_id = fields.Many2one("res.users", string="Thủ quỹ",
                                   default=lambda self: self.env.user.company_id.treasurer.id)
