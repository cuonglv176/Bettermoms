# -*- coding: utf-8 -*-

from odoo import fields, models


class RevenueRecognize(models.Model):
    _name = 'revenue.recognize'
    _description = 'Account Revenue Recognition'

    name = fields.Char(string='uID')
    idItem = fields.Integer(string='idItem')
    idSO = fields.Char(string='idSO')
    idSubItem = fields.Integer(string='idSubItem')
    revenue = fields.Float(string='Revenue')
    revenue_date = fields.Date(string='Revenue Date')
    currencyCode = fields.Char(string='Currency')
    sale_order_id = fields.Many2one("sale.order", string="Sale Order")
    sale_order_line_id = fields.Many2one("sale.order.line",
                                         string="Sale Order Line")
    product_id = fields.Many2one("product.product", string="Product")
    company_id = fields.Many2one("res.company", string="Company")
    state = fields.Selection(
        [('created', 'Created'),
         ('error', 'Fail to create Entry'),
         ('done', 'Done')],
        string="State")
    account_move_id = fields.Many2one("account.move", string="Journal Entry")
    seller_id = fields.Many2one("res.users", string="Seller")

    def update_so_and_company(self):
        # write function here
        print("1")

    def action_post(self):
        # write function here
        print("2")
        x = self.create_journal_entry()
        print(x)

    def create_journal_entry(self):
        journal_id = self.env['account.journal'].sudo().search(
            [('is_revenue_journal', '=', True),
             ('company_id', '=', self.company_id.id)], limit=1)
        print(journal_id)
        print(len(journal_id))

        if len(journal_id) == 0:
            return "revenue account journal is not setup"

        if not self.company_id.id:
            return "Cannot find Company"

        init_so = [
            'tvn_60000001',
            'vl24h_60000002',
            'mw_60000003',
            'vtn_60000004'
        ]

        if not self.sale_order_id.id:
            return "Cannot find order"

        # Check neu khong phai ghi nhan cho dau ky
        if self.sale_order_id.SalesOrderUuid not in init_so:
            if not self.sale_order_line_id.id:
                return "Cannot find order line"

            if not self.product_id.categ_id:
                return "Cannot find product category"

            if not self.product_id.categ_id.\
                    with_company(self.company_id.id).\
                    property_account_income_categ_id.id:
                return "Cannot find account income"

            if not self.product_id.categ_id.\
                    with_company(self.company_id.id).\
                    revenue_recognition_account_id.id:
                return "Cannot find revenue recognition account"

            print("hihihihihi")
            if len(self.sale_order_line_id.invoice_lines) == 0:
                return "Cannot find invoice lines corresponding to order line id " + str(self.sale_order_line_id.id)

            partner_id = self.sale_order_line_id.invoice_lines[0].partner_id.id

            print(partner_id)
            print(">>>>>>>>>>>>>>>>>>>>>")
            # Nếu revenue lon hon 0
            if self.revenue > 0:
                move_vals = {
                    # 'name': self.generate_unique_move_name_by_date(journal_id, self.revenue_date),
                    'journal_id': journal_id.id,
                    'company_id': self.company_id.id,
                    'currency_id': self.sale_order_id.currency_id.id,
                    'date': self.revenue_date,
                    'revenue_recognize_id': self.id,
                    'so_id': self.sale_order_id.id,
                    'line_ids': [
                        (0, 0, {
                            'name': 'debit',
                            'account_id': self.product_id.categ_id.
                            with_company(self.company_id.id).
                            property_account_income_categ_id.id,
                            'debit': self.revenue,
                            'partner_id': partner_id,
                            'credit': 0.0
                        }),
                        (0, 0, {
                            'name': 'credit',
                            'account_id': self.product_id.categ_id.
                            with_company(self.company_id.id).
                            revenue_recognition_account_id.id,
                            'debit': 0.0,
                            'partner_id': partner_id,
                            'credit': self.revenue
                        }),
                    ],
                }
            # neu revenue nho hon 0
            else:
                move_vals = {
                    # 'name': self.generate_unique_move_name_by_date(journal_id, self.revenue_date),
                    'journal_id': journal_id.id,
                    'company_id': self.company_id.id,
                    'currency_id': self.sale_order_id.currency_id.id,
                    'date': self.revenue_date,
                    'revenue_recognize_id': self.id,
                    'so_id': self.sale_order_id.id,
                    'line_ids': [
                        (0, 0, {
                            'name': 'credit',
                            'account_id': self.product_id.categ_id.
                         with_company(self.company_id.id).
                         property_account_income_categ_id.id,
                            'credit': -self.revenue,
                            'partner_id': partner_id,
                            'debit': 0.0
                         }),
                        (0, 0, {
                            'name': 'debit',
                            'account_id': self.product_id.categ_id.
                         with_company(self.company_id.id).
                         revenue_recognition_account_id.id,
                            'credit': 0.0,
                            'partner_id': partner_id,
                            'debit': -self.revenue
                         }),
                    ],
                }

            print(move_vals)

            if not self.account_move_id.id:
                account_move = self.env['account.move'].create(move_vals)
                account_move.action_post()

                if account_move.state == 'posted':
                    self.state = 'done'
                    self.account_move_id = account_move.id
            else:
                line_ids = []
                for move_line in self.account_move_id.line_ids:
                    if move_line.debit > 0:
                        debitItem = (1, move_line.id, {
                            'name': 'debit',
                            'account_id': self.product_id.categ_id.
                            with_company(self.company_id.id).
                            property_account_income_categ_id.id,
                            'debit': self.revenue,
                            'partner_id': partner_id,
                            'credit': 0.0,
                        })
                        line_ids.append(debitItem)
                    elif move_line.credit > 0:
                        creditItem = (1, move_line.id, {
                            'name': 'credit',
                            'account_id': self.product_id.categ_id.
                            with_company(self.company_id.id).
                            revenue_recognition_account_id.id,
                            'debit': 0.0,
                            'partner_id': partner_id,
                            'credit': self.revenue,
                        })
                        line_ids.append(creditItem)
                move_vals['line_ids'] = line_ids
                self.account_move_id.update(move_vals)
            return True
        else:
            account_3387_id = self.env['account.account'].sudo().search(
                [('is_default_3387', '=', True),
                 ('company_id', '=', self.company_id.id)], limit=1)
            account_5113_id = self.env['account.account'].sudo().search(
                [('is_default_5113', '=', True),
                 ('company_id', '=', self.company_id.id)], limit=1)

            partner_id = self.sale_order_id.partner_id.id
            if self.revenue > 0:
                move_vals = {
                    # 'name': self.generate_unique_move_name_by_date(journal_id, self.revenue_date),
                    'journal_id': journal_id.id,
                    'company_id': self.company_id.id,
                    'currency_id': self.sale_order_id.currency_id.id,
                    'date': self.revenue_date,
                    'revenue_recognize_id': self.id,
                    'so_id': self.sale_order_id.id,
                    'line_ids': [
                        (0, 0, {
                            'name': 'debit',
                            'account_id': account_3387_id.id,
                            'debit': self.revenue,
                            'partner_id': partner_id,
                            'credit': 0.0,
                        }),
                        (0, 0, {
                            'name': 'credit',
                            'account_id': account_5113_id.id,
                            'debit': 0.0,
                            'partner_id': partner_id,
                            'credit': self.revenue,
                        }),
                    ],
                }
            else:
                move_vals = {
                    # 'name': self.generate_unique_move_name_by_date(journal_id, self.revenue_date),
                    'journal_id': journal_id.id,
                    'company_id': self.company_id.id,
                    'currency_id': self.sale_order_id.currency_id.id,
                    'date': self.revenue_date,
                    'revenue_recognize_id': self.id,
                    'so_id': self.sale_order_id.id,
                    'line_ids': [
                        (0, 0, {
                            'name': 'credit',
                            'account_id': account_3387_id.id,
                            'credit': -self.revenue,
                            'partner_id': partner_id,
                            'debit': 0.0,
                        }),
                        (0, 0, {
                            'name': 'debit',
                            'account_id': account_5113_id.id,
                            'credit': 0.0,
                            'partner_id': partner_id,
                            'debit': -self.revenue,
                        }),
                    ],
                }

            print(move_vals)

            if not self.account_move_id.id:
                account_move = self.env['account.move'].create(move_vals)
                account_move.action_post()

                if account_move.state == 'posted':
                    self.state = 'done'
                    self.account_move_id = account_move.id
            else:
                line_ids = []
                for move_line in self.account_move_id.line_ids:
                    if move_line.debit > 0:
                        debitItem = (1, move_line.id, {
                            'name': 'debit',
                            'account_id': self.product_id.categ_id.
                            with_company(self.company_id.id).
                            property_account_income_categ_id.id,
                            'debit': self.revenue,
                            'partner_id': partner_id,
                            'credit': 0.0,
                        })
                        line_ids.append(debitItem)
                    elif move_line.credit > 0:
                        creditItem = (1, move_line.id, {
                            'name': 'credit',
                            'account_id': self.product_id.categ_id.
                            with_company(self.company_id.id).
                            revenue_recognition_account_id.id,
                            'debit': 0.0,
                            'partner_id': partner_id,
                            'credit': self.revenue,
                        })
                        line_ids.append(creditItem)
                move_vals['line_ids'] = line_ids
                self.account_move_id.update(move_vals)
            return True

    def generate_unique_move_name_by_date(self, journal, date):
        month = date.strftime("%m")
        year = date.strftime("%Y")
        journal_code = journal.code

        name_part1 = journal_code + '/' + year + '/' + month
        # moves = self.env['account.move'].sudo().search([('name', 'like', name_part1)], order=" substring(account_move.name,'([^/]+)/?$')::int DESC")

        query = '''
                    Select name, substring(account_move.name, '([^/]+)/?$')::int  from account_move
                    Where name Like '%(name)s'
                    Order By substring(account_move.name,'([^/]+)/?$')::int DESC
                '''
        query = query % ({
            'name': '%'+name_part1+'%'
        })
        self.env.cr.execute(query)

        name_part2 = ''
        records = self.env.cr.fetchall()
        if records:
            for record in records:
                name_part2 = str(record[1] + 1)
                break
        else:
            name_part2 = '00001'

        # if len(moves.ids) > 0:
        #     name_part2 = str(int(moves[0].name.split('/')[-1])+1)
        # else:
        #     name_part2 = '00001'

        return name_part1 + '/' + name_part2
