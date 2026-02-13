# __author__ = 'BinhTT'
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import ast
def build_table_result(data_list: dict):
    template = """
        <style>
            .styled-table {
                border-collapse: collapse;
                // margin: 25px 0;
                font-family: sans-serif;
                min-width: 400px;
                width: 100%;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            }
            .styled-table thead tr {
                background-color: #714B67;
                color: #f6f7fa;
                text-align: left;
            }
            .styled-table th, .styled-table td {
                padding: 3px 10px;
            }
            .styled-table tbody tr {
                border-bottom: 1px solid #dddddd;
            }

            .styled-table tbody tr:nth-of-type(even) {
                background-color: #f3f3f3;
            }

            .styled-table tbody tr:last-of-type {
                border-bottom: 2px solid #714B67;
                background-color: #714B67;
                color: #f6f7fa;
            }

            .styled-table tbody tr.to_reconcile {
                color: red;
            }
        </style>

        <table class="styled-table">
        <thead>
            <tr>
                <td style="min-width: 90px">Tax Name</td>
                <td>Amount</td>
            </tr>
        </thead>
        <tbody>
    """
    # <td>Type</td>

    total = 0
    for key, row in data_list.items():
        data = f"""
        <tr class="">
            <td>{row['name']}</td>
            <td>{"{:,.0f}". format(abs(row['balance']))}</td>
        </tr>
        """.strip()
        # < td > {row['type']} < / td >

        total += abs(row["balance"])
        template += data
    template += f"""
        <tr class="">
            <td>Total</td>
            <td>{"{:,.0f}". format(abs(total))}</td>
        </tr>
        """.strip()
    template += "</tbody></table>"
    return template


class NTPPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    tax_summary = fields.Text(compute='get_tax_summary')
    vat_data = fields.Text(compute='get_tax_summary')
    create_vat_bill = fields.Boolean(compute='get_tax_summary')
    purchase_landed_ids = fields.One2many('purchase.landed.cost', 'purchase_id', compute='get_bill_landed_cost')
    purchase_landed_valuation_ids = fields.One2many('purchase.landed.valuation', 'purchase_id', compute='get_bill_landed_cost')

    def get_bill_landed_cost(self):
        self.purchase_landed_ids = False
        self.purchase_landed_valuation_ids = False
        bill_landed = self.env['account.move']
        for invoice in self.invoice_ids.filtered(lambda x:x.state =='posted'):
            if invoice.invoice_line_ids.filtered(lambda x:x.is_landed_costs_line):
                bill_landed += invoice
        bill_landed -= self.purchase_landed_ids.bill_id
        for bill in bill_landed:
            self.create_purchase_landed_cost(bill)

        if self.picking_ids and self.purchase_landed_ids:
            for line in self.picking_ids[0].move_lines:
                qty = line.stock_valuation_layer_ids and line.stock_valuation_layer_ids[0].quantity or (line.product_qty)
                original_value = line.stock_valuation_layer_ids and line.stock_valuation_layer_ids[0].value or (line.price_unit * line.product_qty)
                vals = {'product_id': line.product_id.id,
                        'original_value': original_value,
                        'qty': qty,
                        'unit_cost': line.stock_valuation_layer_ids and line.stock_valuation_layer_ids[0].unit_cost or (line.price_unit),
                        'purchase_id': self.id}
                additional_value = 0
                for valuation in self.purchase_landed_ids.landed_costs_ids.valuation_adjustment_lines.filtered(lambda x:x.product_id == line.product_id):
                    additional_value += valuation.additional_landed_cost
                vals.update(additional_value=additional_value, new_value=original_value + additional_value,
                            new_cost=(original_value + additional_value) / qty,
                            additional_unit_price=additional_value / qty)
                self.env['purchase.landed.valuation'].create(vals)

        return


    def create_purchase_landed_cost(self, bill):
        total = 0
        for line in bill.invoice_line_ids.filtered(lambda x:x.is_landed_costs_line):
            total += line.balance
            # if line.currency_id != line.company_id.currency_id:
            #     if bill.exchange_rate:
            #         price_unit = price_unit * bill.exchange_rate
            #     else:
            #         price_unit = bill.currency_id._convert(
            #             price_unit, bill.company_id.currency_id, bill.company_id, fields.Date.context_today(self),
            #             round=False)
            # total += price_unit
        res = {
            'bill_id': bill.id,
            'total': total,
            'purchase_id': self.id,
            'landed_costs_ids': bill.landed_costs_ids.ids,
            'had_landed_costs': (bill.landed_costs_ids.ids and True) or False
        }

        self.env['purchase.landed.cost'].create(res)

    def create_vendor_bill_tax(self):
        """Create the invoice associated to the PO.
                """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Prepare invoice vals and clean-up the section lines
        invoice_vals_list = []
        for order in self:
            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            invoice_vals = order._prepare_invoice()
            invoice_vals.update(currency_id=self.env.company.currency_id.id)
            # Invoice line values (keep only necessary sections).
            for tag_id, value in ast.literal_eval(order.vat_data).items():
                tag_obj = self.env['account.account.tag'].browse(tag_id)
                if not tag_obj.account_id:
                    continue
                value.update(account_id=tag_obj.account_id.id, is_landed_costs_line=tag_obj.product_id.landed_cost_ok,
                             product_id=tag_obj.product_id.id)
                invoice_vals['invoice_line_ids'].append((0, 0, self._prepare_vat_move_line(value)))
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(
                _('There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received.'))

        # 3) Create invoices.
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice')
        for vals in invoice_vals_list:
            moves |= AccountMove.with_company(vals['company_id']).create(vals)
        return self.action_view_invoice(moves)

    def _prepare_vat_move_line(self, value={}):
        self.ensure_one()
        aml_currency = self.env.company.currency_id
        date = fields.Date.today()
        res = {
            'name': '%s' % (value.get('name')),
            'product_id': value.get('product_id'),
            'product_uom_id': False,
            'quantity': 1,
            'price_unit': abs(value.get('balance')),
            'tax_ids': [(6, 0, [])],
            'is_landed_costs_line': value.get('is_landed_costs_line'),
            'analytic_account_id': False,
            'analytic_tag_ids': [(6, 0, [])],
            'account_id': value.get('account_id'),
        }

        return res

    def get_tax_summary(self):
        self.tax_summary = self.vat_data = ''
        self.create_vat_bill = False
        tax_data = {}
        for line in self.invoice_ids.filtered(lambda x:x.state =='posted').line_ids.filtered(lambda x:x.tax_tag_ids):
            if line.tax_tag_ids[0].id not in tax_data:
                tax_data.setdefault(line.tax_tag_ids[0].id, {'name': line.tax_tag_ids[0].name, 'balance': 0, 'type': line.tax_tag_ids[0].vat_type.name or ''})
            tax_data[line.tax_tag_ids[0].id]['balance'] += line.balance

        # for line in self.invoice_ids.line_ids.filtered(lambda x:x.tax_tag_ids.vat_type):
        #     if line.tax_tag_ids[0].vat_type.id not in tax_data:
        #         tax_data.setdefault(line.tax_tag_ids[0].vat_type.id, {'name': line.tax_tag_ids[0].vat_type.name, 'balance': 0})
        #     tax_data[line.tax_tag_ids[0].vat_type.id]['balance'] += line.balance
        if tax_data:
            self.tax_summary = build_table_result(tax_data)
            self.vat_data = tax_data
        vat_type = {}
        for line in self.invoice_ids.filtered(lambda x:x.state =='posted').line_ids.filtered(lambda x:x.tax_tag_ids.vat_type):
            if line.tax_tag_ids[0].vat_type.id not in vat_type:
                vat_type.setdefault(line.tax_tag_ids[0].vat_type.id, {'name': line.tax_tag_ids[0].vat_type.name, 'balance': 0, 'type': ''})
            vat_type[line.tax_tag_ids[0].vat_type.id]['balance'] += line.balance
        if vat_type:
            self.tax_summary += build_table_result(vat_type)
            self.create_vat_bill = True
        return