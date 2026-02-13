# -*- coding: utf-8 -*-

from odoo import fields, models, api
from num2words import num2words
from odoo.tools.misc import get_lang


class AccountMove(models.Model):
    _inherit = 'account.move'

    tas_type = fields.Selection([
        ('inbound', 'Phiếu Thu'),
        ('outbound', 'Phiếu Chi'),
        ('debit', 'Giấy báo nợ'),
        ('credit', 'Giấy báo có'),
        ('other', 'Chứng từ kế toán'),
    ], 'Loại Phiếu', default='other')

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

    @api.onchange('tas_type')
    def _onchange_tas_type(self):
        if self.tas_type and self.tas_type in ('debit', 'credit'):
            self.journal_id = False
            return {'domain': {'journal_id': [('type', 'in', ['bank', 'cash'])]}}

    def action_create_ma_phieu(self):
        self.manager_id = self.journal_id.manager_id
        self.accountant_id = self.journal_id.accountant_id
        self.treasurer_id = self.journal_id.treasurer_id
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        if len(self.payment_id) > 0:
            if self.payment_id.payment_type == 'inbound':
                if self.payment_id.journal_id.type == 'cash':
                    self.tas_type = 'inbound'
                else:
                    self.tas_type = 'credit'
            if self.payment_id.payment_type == 'outbound':
                if self.payment_id.journal_id.type == 'cash':
                    self.tas_type = 'outbound'
                else:
                    self.tas_type = 'debit'

        if self.tas_type == 'inbound' or self.tas_type == 'credit':
            self.ma_phieu_in = self.journal_id.pt_sequence_id.next_by_id()

        if self.tas_type == 'outbound' or self.tas_type == 'debit':
            self.ma_phieu_in = self.journal_id.pc_sequence_id.next_by_id()

        print(self.payment_id)
        print(self.payment_id.payment_type)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    @api.depends('amount_total')
    def _compute_tien_bang_chu(self):
        for record in self:
            try:
                record.money_char = num2words(record.amount_total, lang=get_lang(self.env).code).capitalize() + " " + record.currency_id.name
            except NotImplementedError:
                record.money_char = num2words(record.amount_total, lang='en').capitalize() + " VND."

            # if record.journal_id.type == "cash":
            #     record.tas_type = 'inbound'
            #     record.ma_phieu_in = ""
            # else:
            #     record.tas_type = 'other'
            #     record.ma_phieu_in = "PC/123"

    #         debitaccount = ""
    #         creditaccount = ""
    #         for line in record.line_ids:
    #             if (line.debit == 0) and (line.credit >0):
    #                 if creditaccount == "":
    #                     creditaccount += line.account_id.code
    #                 else:
    #                     creditaccount += ", "+line.account_id.code
    #             if (line.credit == 0) and (line.debit >0):
    #                 if debitaccount == "":
    #                     debitaccount += line.account_id.code
    #                 else:
    #                     debitaccount += ", "+line.account_id.code
    #         record.vn_debit_account = debitaccount
    #         record.vn_credit_account = creditaccount

    @api.depends('company_id', 'invoice_filter_type_domain')
    def _compute_suitable_journal_ids(self):
        super(AccountMove, self)._compute_suitable_journal_ids()

        for m in self:
            if m.tas_type == 'inbound' or m.tas_type == 'outbound' or m.tas_type == 'debit' or m.tas_type == 'credit':
                domain = [('company_id', '=', m.company_id.id), ('type', 'in', ['general', 'bank', 'cash'])]
                m.suitable_journal_ids = self.env['account.journal'].search(domain)

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.tas_type != 'other' and res.journal_id.id:
            res.action_create_ma_phieu()
        return res