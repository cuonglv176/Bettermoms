# __author__ = 'BinhTT'

from odoo import models, fields, api
import re


class AccountMoveLineVAS(models.Model):
    _inherit = "account.move.line"

    # tax_bill_total_amount_with_vat = fields.Monetary(
    #     "Registered Amt w/ VAT", compute="_compute_tax_bill_info", store=False
    # )
    odoo_amount = fields.Float(
        "Odoo Amount", compute="_compute_tax_bill_info", store=False
    )
    einvoice_amount = fields.Float(
        "E-Invoice Amount", compute="_compute_tax_bill_info", store=False
    )
    residual_mismatch = fields.Float(
            "Residual Mismatched", compute="_compute_tax_bill_info", store=False
        )
    # registered_date = fields.Date("Registered Date", compute="_compute_tax_bill_info", store=False)
    registered_mismatch = fields.Boolean("Mismatched", compute="_compute_tax_bill_info", store=True)
    ignore_mismatch = fields.Boolean(string="Ignore Mismatch")
    reason_ignore_mismatch = fields.Char(string="Reason Ignore Mismatch")

    def action_open_ignore_mismatch(self):
        ctx = self.env.context.copy()
        ctx.update({
            'move_line_ids': self.ids
        })
        return {
            'name': "Reason Ignore Mismatch",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'wizard.ignore.mismatch',
            'target': 'new',
            'context': ctx,
        }

    @api.depends('move_id.tax_invoice_ids', 'move_id.einvoice_ids', 'residual_mismatch')
    def _compute_tax_bill_info(self):
        for r in self:
            r.residual_mismatch = r.odoo_amount = r.einvoice_amount = 0
            r.registered_mismatch = False
            if r.env.context.get('compute_mismatch', False):
                vat_percent = int(re.search(r'\d+', r.tax_tag_ids.tax_group.name or r.tax_ids.tax_group_id.name).group())
                if r.move_id.tax_invoice_ids and not r.ignore_mismatch:
                    for line in r.move_id.tax_invoice_ids.tax_invoice_lines.filtered(lambda x: x.vat_percentage == vat_percent):
                        r.residual_mismatch += line.total_price_before_vat if r.tax_ids else line.total_price_after_vat - line.total_price_before_vat
                        r.einvoice_amount += line.total_price_before_vat if r.tax_ids else line.total_price_after_vat - line.total_price_before_vat

                    # case 1: 1 invoice have many tax invoice
                    if len(r.move_id.tax_invoice_ids.account_move_ids) == 1:
                        for bill_line in r.move_id.line_ids.filtered(lambda x: x.tax_tag_ids.tax_group.name and int(re.search(r'\d+', x.tax_tag_ids.tax_group.name).group()) == vat_percent):
                            if bill_line.tax_ids == r.tax_ids:
                                r.residual_mismatch -= bill_line.balance
                                r.odoo_amount += bill_line.balance
                    # case 2:many invoice have 1 tax invoice
                    else:
                        for bill_line in r.move_id.tax_invoice_ids.account_move_ids.line_ids.filtered(lambda x: x.account_id == r.account_id):
                            r.residual_mismatch -= bill_line.balance
                            r.odoo_amount += bill_line.balance
                    if r.rounding_mismatch():
                        r.registered_mismatch = True

                    # r.registered_date = invoice.issued_date

                elif r.move_id.einvoice_ids and not r.ignore_mismatch:
                    r.registered_mismatch = False
                    for invoice in r.move_id.einvoice_ids.filtered(lambda x: x.vat_percent == vat_percent):
                        r.residual_mismatch += invoice.total_vat_amount if not r.tax_ids else invoice.total_amount_with_vat - invoice.total_vat_amount
                        for bill_line in r.move_id.line_ids.filtered(lambda x: x.tax_tag_ids.tax_group.name and int(
                                re.search(r'\d+', x.tax_tag_ids.tax_group.name).group()) == vat_percent):
                            if bill_line.tax_ids == r.tax_ids:
                            #     r.tax_bill_total_amount_without_vat -= abs(bill_line.balance)
                            # elif not bill_line.tax_ids:
                                r.residual_mismatch -= abs(bill_line.balance)
                        if r.rounding_mismatch():
                            r.registered_mismatch = True
                        # r.registered_date = invoice.issue_date

                else:
                    r.registered_mismatch = True
                    r.residual_mismatch = r.balance if not r.ignore_mismatch else 0
                    r.odoo_amount = r.balance
                    if not r.ignore_mismatch:
                        r.reason_ignore_mismatch = 'No E-Invoice'
                    # if (r.tax_ids and r.tax_bill_total_amount_without_vat != abs(r.balance)) or \
            #         (not r.tax_ids and r.tax_base_amount != r.tax_bill_total_amount_without_vat):
            #     r.registered_mismatch = True

    def rounding_mismatch(self):
        # if abs(self.residual_mismatch) < 10:
        #     self.residual_mismatch = 0
        #     return False
        return self.residual_mismatch