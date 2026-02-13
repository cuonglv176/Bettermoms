from datetime import date, datetime, timedelta
import json
import logging
from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError
from ..utils.invoice_table import InvoiceTable
import traceback

logger = logging.getLogger(__name__)


DATE_FORMAT_JSON_DUMP = "%Y-%m-%d"


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[
            ("delivered_sliced", "Regular Invoice Sliced"),
        ],
        ondelete={"delivered_sliced": "set default"},
    )
    sliced_invoices_data = fields.Text()
    sliced_invoices_data_display = fields.Text(
        compute="_compute_sliced_invoices_data_display"
    )

    @api.onchange("advance_payment_method")
    def onchange_advance_payment_method(self):
        data = super().onchange_advance_payment_method()
        if self.advance_payment_method == "delivered_sliced":
            if not data:
                data = {"value": {}}
            try:
                sliced_invoice_data = self.generate_sliced_invoice()
                if sliced_invoice_data:
                    self.sliced_invoices_data = json.dumps(sliced_invoice_data)
                    self._compute_sliced_invoices_data_display()
                    data["value"].update(
                        {
                            "sliced_invoices_data": self.sliced_invoices_data,
                            "sliced_invoices_data_display": self.sliced_invoices_data_display,
                        }
                    )
            except Exception as e:
                sliced_invoice_data = None
                data["value"].update(
                    {
                        "sliced_invoices_data": False,
                        "sliced_invoices_data_display": f"<p style='color: red'>Error When Generate Sliced Invocies:</p><pre>{traceback.format_exc()}</pre>",
                    }
                )
        return data

    def _build_sliced_invoices_data_display_table(
        self, sliced_invoice_policy_id: int, start_date_to_invoice: date, invoices: list
    ):
        def _get_invoice_items_description(invoice):
            total_amount = 0
            txt = ""
            for _id, (so_line_id, qty) in enumerate(invoice, start=1):
                so_line = self.env["sale.order.line"].browse([so_line_id])
                taxed_pu = self._get_price_unit_with_tax_so_line(so_line_id)
                price_total = taxed_pu * qty
                total_amount += price_total
                taxed_pu_printed = tools.format_amount(
                    self.env, taxed_pu, so_line.currency_id
                )
                price_total_printed = tools.format_amount(
                    self.env, price_total, so_line.currency_id
                )
                txt += f"<span>{_id}. {so_line.name} / {taxed_pu_printed} * {qty} = {price_total_printed}</span><br/>"
            return total_amount, txt

        # when we reload the form
        sale_orders = self.env["sale.order"].browse(self._context.get("active_ids", []))
        sale_orders.ensure_one()

        template = """
            <h4><b>{member_info}</b></h4>
            <table class="styled-table">
            <thead>
                <tr>
                    <td>Issue Date</td>
                    <td>Invoice Items</td>
                    <td>Total Amount</td>
                </tr>
            </thead>
            <tbody>
        """
        member = (
            self.env["so.to.sliced.invoices"]
            .browse([sliced_invoice_policy_id])
            .member_id
        )
        # TODO: get xlated selection text, not upper()
        template = template.format(
            member_info="{} / {}".format(member.group_type.upper(), member.name)
        )
        grand_total = 0

        for _id, invoice in enumerate(invoices):
            total_amount, items_desc = _get_invoice_items_description(invoice)
            grand_total += total_amount
            total_amount_printed = tools.format_amount(
                self.env, total_amount, sale_orders.currency_id
            )
            invoice_date = start_date_to_invoice + timedelta(days=_id)
            data = f"""
            <tr>
                <td>{invoice_date.strftime('%Y-%m-%d')}</td>
                <td>{items_desc}</td>
                <td>{total_amount_printed}</td>
            </tr>
            """.strip()
            template += data
        grand_total_printed = tools.format_amount(
            self.env, grand_total, sale_orders.currency_id
        )
        template += f"""
            <tr>
                <td></td>
                <td style="text-align: right"><b>({len(invoices)} Invoices) Grand Total</b></td>
                <td>{grand_total_printed}</td>
            </tr>
            """.strip()
        template += "</tbody></table>"
        return template

    def _compute_sliced_invoices_data_display(self):
        for rec in self:
            rec.sliced_invoices_data_display = ""
            if rec.sliced_invoices_data:
                sliced_invoices_data = json.loads(rec.sliced_invoices_data)
                sliced_invoices_data_display = """
<style>
    .styled-table {
        border-collapse: collapse;
        margin: 25px 0;
        font-family: sans-serif;
        min-width: 400px;
        width: 100%;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
    }
    .styled-table thead tr {
        background-color: #009879;
        color: #ffffff;
        text-align: left;
    }
    .styled-table th, .styled-table td {
        padding: 3px 10px;
    }
    .styled-table th, .styled-table tr td:last-of-type {
        text-align: right;
    }
    .styled-table tbody tr {
        border-bottom: 1px solid #dddddd;
    }

    .styled-table tbody tr:nth-of-type(even) {
        background-color: #f3f3f3;
    }

    .styled-table tbody tr:last-of-type {
        border-bottom: 2px solid #009879;
    }
</style>
                """
                for (
                    member_policy_id,
                    start_date_to_invoice,
                    invoices,
                ) in sliced_invoices_data:
                    start_date_to_invoice = datetime.strptime(
                        start_date_to_invoice, DATE_FORMAT_JSON_DUMP
                    )
                    sliced_invoices_data_display += (
                        self._build_sliced_invoices_data_display_table(
                            member_policy_id, start_date_to_invoice, invoices
                        )
                    )
                rec.sliced_invoices_data_display = sliced_invoices_data_display

    def generate_sliced_invoice(self):
        sale_orders = self.env["sale.order"].browse(self._context.get("active_ids", []))
        sale_orders.ensure_one()
        start_date_to_invoice = sale_orders.so_to_sliced_invoice_start_date
        if self.advance_payment_method == "delivered_sliced":
            # we need to test which is invoiced then get the list of product with quantity invoiced in normal way
            # after that, do water fill algorithm to slice original invoice to multiple ones
            self._cr.execute("SAVEPOINT delivered_sliced_get_original_invoices")
            invoices = sale_orders._create_invoices(final=self.deduct_down_payments)
            original_invoice_lines = []
            invoiced_invoice_lines = []
            for line in invoices.line_ids:
                if line.product_id:
                    original_invoice_lines.append(
                        [line.sale_line_ids[0].id, line.quantity]
                    )
                    invoiced_invoice_lines.append([line.sale_line_ids[0].id, 0])
            self._cr.execute(
                "ROLLBACK TO SAVEPOINT delivered_sliced_get_original_invoices"
            )
            if len(invoices) > 1:
                raise UserError("cannot slice if system generate more than 1 invoice")
            print(original_invoice_lines)

            # # TODO: we will have problem if we slice invoice with order line UoM not integer, so keep in mind
            # # TODO: from now on, we force quantity = integer, and fix this issue later
            sliced_invoice_data = []
            for sliced_invoice_policy in sale_orders.so_to_sliced_invoices_ids:
                invoices = self._prepare_invoice_for_member(
                    original_invoice_lines,
                    invoiced_invoice_lines,
                    sliced_invoice_policy,
                )
                sliced_invoice_data.append(
                    [
                        sliced_invoice_policy.id,
                        start_date_to_invoice.strftime(DATE_FORMAT_JSON_DUMP),
                        invoices,
                    ]
                )
            total_remain_to_invoice = self._get_total_remain_to_invoice(
                original_invoice_lines, invoiced_invoice_lines
            )
            if total_remain_to_invoice:
                raise UserError(
                    "cannot invoice all invoicable items. need to check algorithm"
                )
            return sliced_invoice_data
        else:
            raise UserError(
                "cannot perform this action if not choosing 'delivered_sliced'"
            )

    def button_preview_sliced_invoice(self):
        sliced_invoice_data = self.generate_sliced_invoice()
        if sliced_invoice_data:
            self.sliced_invoices_data = json.dumps(sliced_invoice_data)
        self._cr.commit()
        return {
            "type": "ir.actions.act_window",
            # "name": "Preview EInvoice Before Create It",
            "res_model": "sale.advance.payment.inv",
            "res_id": self.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": self._context.copy(),
        }

    def _calc_total_amount(self, original_invoice_lines):
        total = 0
        for so_line_id, quantity in original_invoice_lines:
            so_line = self.env["sale.order.line"].browse([so_line_id])
            so_line_total = so_line.price_total / so_line.product_uom_qty * quantity
            total += so_line_total
        return total

    def _get_price_unit_with_tax_so_line(self, so_line_id):
        so_line = self.env["sale.order.line"].browse([so_line_id])
        return so_line.price_total / so_line.product_uom_qty

    def _find_suitable_order_line(
        self, original_invoice_lines, invoiced_invoice_lines, remaining_to_invoice
    ):
        for _, (original_line, invoiced_line) in enumerate(
            zip(original_invoice_lines, invoiced_invoice_lines)
        ):
            remain_qty = original_line[1] - invoiced_line[1]
            if remain_qty:
                # available to add
                taxed_pu = self._get_price_unit_with_tax_so_line(original_line[0])
                qty = int(remaining_to_invoice / taxed_pu)
                if qty:
                    if qty > remain_qty:
                        qty = remain_qty
                    return original_line[0], qty
        return None, None

    def _get_total_remain_to_invoice(
        self, original_invoice_lines, invoiced_invoice_lines
    ):
        max_total_to_invoice = 0
        for _, (original_line, invoiced_line) in enumerate(
            zip(original_invoice_lines, invoiced_invoice_lines)
        ):
            taxed_pu = self._get_price_unit_with_tax_so_line(original_line[0])
            total_invoice_line = taxed_pu * (original_line[1] - invoiced_line[1])
            max_total_to_invoice += total_invoice_line
        return max_total_to_invoice

    def _is_invoicable_with_total_remain(
        self, original_invoice_lines, invoiced_invoice_lines, remain_total_to_invoice
    ):
        """check that with this amount, can any item in sale order can be invoiced"""
        for _, (original_line, invoiced_line) in enumerate(
            zip(original_invoice_lines, invoiced_invoice_lines)
        ):
            remaining_qty = original_line[1] - invoiced_line[0]
            taxed_pu = self._get_price_unit_with_tax_so_line(original_line[0])
            if remaining_qty and int(remain_total_to_invoice / taxed_pu) != 0:
                return True
        return False

    def _prepare_invoice_for_member(
        self, original_invoice_lines, invoiced_invoice_lines, sliced_invoice_policy
    ):
        # STEP 1: calc how much can be invoiced under this member
        total_amount_invoiced = self._calc_total_amount(original_invoice_lines)
        if sliced_invoice_policy.quota_unit == "amount":
            max_total_to_invoice = sliced_invoice_policy.quota_to_invoice
        elif sliced_invoice_policy.quota_unit == "percent":
            max_total_to_invoice = (
                total_amount_invoiced * sliced_invoice_policy.quota_to_invoice / 100
            )
        else:
            # by balance
            # calc total_remain to invoice
            max_total_to_invoice = self._get_total_remain_to_invoice(
                original_invoice_lines, invoiced_invoice_lines
            )
            logger.info("remaining for balance = {}".format(max_total_to_invoice))

        # STEP 2: calc how much can be invoiced in single invoice
        #         check how many invoice can be invoiced (max number)
        if sliced_invoice_policy.max_total_amount_per_invoice:
            max_total_amount_per_invoice = (
                sliced_invoice_policy.max_total_amount_per_invoice
            )
        else:
            # since dont set limit per invoice, so just create 1 invoice only
            # also max amount to invoice is its quota
            max_total_amount_per_invoice = max_total_to_invoice

        # fillup product list can be invoiced to this sub
        invoices = []
        total_amount_invoiced = 0
        while total_amount_invoiced < max_total_to_invoice:
            invoice_table = InvoiceTable(self.env)
            remain_total_to_invoice = max_total_to_invoice - total_amount_invoiced
            # ! normally willbe max_total_amount_per_invoice
            # ! but in the last time we issue invoice, residual amount may be different
            current_amount_to_invoice = min(
                max_total_amount_per_invoice, remain_total_to_invoice
            )
            if not self._is_invoicable_with_total_remain(
                original_invoice_lines, invoiced_invoice_lines, remain_total_to_invoice
            ):
                logger.info(
                    f"remaining amount to invoice is too less ({remain_total_to_invoice}), cannot invoice any items"
                )
                break
            while invoice_table.get_total_amount() <= current_amount_to_invoice:
                remaining_to_invoice = (
                    current_amount_to_invoice - invoice_table.get_total_amount()
                )
                # find suitable product to fill
                sale_line_id, quantity = self._find_suitable_order_line(
                    original_invoice_lines=original_invoice_lines,
                    invoiced_invoice_lines=invoiced_invoice_lines,
                    remaining_to_invoice=remaining_to_invoice,
                )
                if sale_line_id and quantity:
                    # recursive lookup
                    invoice_table.add_sale_line_id(sale_line_id, quantity)
                    # update invoiced_invoice_lines_copy
                    for _id, data in enumerate(invoiced_invoice_lines):
                        if data[0] == sale_line_id:
                            invoiced_invoice_lines[_id][1] += quantity
                else:
                    if invoice_table.get_sale_line_ids():
                        invoices.append(invoice_table.get_sale_line_ids())
                        # grand total invoiced
                        total_amount_invoiced += invoice_table.get_total_amount()
                    break
        return invoices

    # override create_invoices to create sliced invoices
    def create_invoices(self):
        if self.advance_payment_method == "delivered_sliced":
            # create sliced invoices here
            sliced_invoice_data = self.generate_sliced_invoice()
            sale_orders = self.env["sale.order"].browse(
                self._context.get("active_ids", [])
            )
            invoices_to_create = []
            for _, (slice_policy_id, start_date_to_invoice, invoices) in enumerate(
                sliced_invoice_data
            ):
                start_date_to_invoice = datetime.strptime(
                    start_date_to_invoice, DATE_FORMAT_JSON_DUMP
                )
                for _id, invoice in enumerate(invoices):
                    invoice_date = start_date_to_invoice + timedelta(days=_id)
                    invoices_to_create.append(
                        self._prepare_member_invoice(
                            sale_orders, invoice_date, slice_policy_id, invoice
                        )
                    )
            # copied from odoo/addons/sale/models/sale_orders.py/SaleOrder/_create_invoices
            moves = (
                self.env["account.move"]
                .sudo()
                .with_context(default_move_type="out_invoice")
                .create(invoices_to_create)
            )
            for move in moves:
                move.message_post_with_view(
                    "mail.message_origin_link",
                    values={
                        "self": move,
                        "origin": move.line_ids.mapped("sale_line_ids.order_id"),
                    },
                    subtype_id=self.env.ref("mail.mt_note").id,
                )
            if self._context.get("open_invoices", False):
                return sale_orders.action_view_invoice()
            return {"type": "ir.actions.act_window_close"}
        else:
            return super().create_invoices()

    def _prepare_member_invoice(
        self, sale_orders, invoice_date, slice_policy_id, invoice
    ):
        slice_policy_id = self.env["so.to.sliced.invoices"].browse(slice_policy_id)
        data = sale_orders._prepare_invoice()
        data.update(
            {
                "invoice_date": invoice_date,
                "partner_id": slice_policy_id.member_id.id,
                "partner_shipping_id": slice_policy_id.member_id.id,
            }
        )

        items = []
        for _id, (so_line_id, qty) in enumerate(invoice):
            so_line = self.env["sale.order.line"].browse(so_line_id)
            item = so_line._prepare_invoice_line(quantity=qty, sequence=_id)
            items.append(item)

        for item in items:
            data["invoice_line_ids"].append([0, 0, item])

        return data
