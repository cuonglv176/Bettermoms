# -*- coding: utf-8 -*-

from odoo import fields, models, api
from num2words import num2words


class AccountMove(models.Model):
    _inherit = 'account.move'

    move_type = fields.Selection(selection_add=[
        ('inbound', 'Phiếu Thu'),
        ('outbound', 'Phiếu Chi'),
        ('debit', 'Giấy báo nợ'),
        ('credit', 'Giấy báo có'),
        ('other', 'Chứng từ kế toán'),
    ], ondelete={
        'inbound': 'set default',
        'outbound': 'set default',
        'debit': 'set default',
        'credit': 'set default',
        'other': 'set default'
    }, string='Loại Phiếu', default='other')

    money_char = fields.Char("Tiền ghi bằng chữ", compute='_compute_tien_bang_chu')
    ma_phieu_in = fields.Char("Mã Phiếu In")
    origin = fields.Char('Chứng từ gốc')
    kemtheo = fields.Integer("Kèm theo")
    lydo = fields.Char("Lý do")
    address = fields.Char("Địa chỉ")
    nguoi_lap = fields.Many2one("res.users", string="Người lập", default=lambda self: self.env.user)
    nguoi_nhan = fields.Char("Người nhận")
    manager_id = fields.Many2one("res.users", string="Tổng giám đốc")
    accountant_id = fields.Many2one("res.users", string="Kế toán trưởng")
    treasurer_id = fields.Many2one("res.users", string="Thủ quỹ")
    team_id = fields.Many2one('crm.team', related='invoice_user_id.sale_team_id', store=True)

    def action_create_ma_phieu(self):
        self.manager_id = self.journal_id.manager_id
        self.accountant_id = self.journal_id.accountant_id
        self.treasurer_id = self.journal_id.treasurer_id
        if len(self.payment_id) > 0:
            if self.payment_id.payment_type == 'inbound':
                if self.payment_id.journal_id.type == 'cash':
                    self.move_type = 'inbound'
                else:
                    self.move_type = 'credit'
            if self.payment_id.payment_type == 'outbound':
                if self.payment_id.journal_id.type == 'cash':
                    self.move_type = 'outbound'
                else:
                    self.move_type = 'debit'

        if self.move_type == 'inbound' or self.move_type == 'credit':
            self.ma_phieu_in = self.journal_id.pt_sequence_id.next_by_id()

        if self.move_type == 'outbound' or self.move_type == 'debit':
            self.ma_phieu_in = self.journal_id.pc_sequence_id.next_by_id()

    @api.depends('amount_total')
    def _compute_tien_bang_chu(self):
        for record in self:
            try:
                record.money_char = num2words(record.amount_total, lang='vi_VN').capitalize() + " đồng chẵn."
            except NotImplementedError:
                record.money_char = num2words(record.amount_total, lang='en').capitalize() + " VND."

    @api.depends('company_id', 'invoice_filter_type_domain')
    def _compute_suitable_journal_ids(self):
        super(AccountMove, self)._compute_suitable_journal_ids()

        for m in self:
            if m.move_type == 'inbound' or m.move_type == 'outbound' or m.move_type == 'debit' or m.move_type == 'credit':
                domain = [('company_id', '=', m.company_id.id), ('type', 'in', ['general', 'bank', 'cash'])]
                m.suitable_journal_ids = self.env['account.journal'].search(domain)

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type != 'other' and res.journal_id.id:
            res.action_create_ma_phieu()
        return res
