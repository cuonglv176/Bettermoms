from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    einvoice_ids = fields.Many2many("ntp.einvoice", copy=False)
    einvoice_ids_count = fields.Integer(compute="_compute_einvoice_ids_count")

    def _compute_einvoice_ids_count(self):
        for rec in self:
            rec.einvoice_ids_count = len(rec.einvoice_ids)

    def button_open_einvoices(self):
        context = self.env.context.copy()
        action = {
            "name": _("EInvoices"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "ntp.einvoice",
            "view_mode": "tree,form",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [("account_move_ids", "=", self.ids)],
            "target": "current",
        }
        return action

    def button_open_einvoice_create_wizard(self):
        wizard = self.env["ntp.einvoice.create"].create(
            {
                "account_move_id": self.id,
                "einvoice_template_id": self.env["ntp.einvoice.template"]
                .search([("is_active", "=", True), ("is_default", "=", True)])
                .id
                or False,
            }
        )
        return {
            "name": _("EInvoices"),
            "type": "ir.actions.act_window",
            "res_model": "ntp.einvoice.create",
            "res_id": wizard.id,
            "views": [[False, "form"]],
            "target": "new",
        }

    def button_create_einvoice(self, einvoice_template_id=None):
        # now just allow single invoice created from this button
        if self.einvoice_ids_count > 0:
            raise UserError(
                "Already created. Please Click On EInvoice Stat Box to see !"
            )

        einvoices = []
        # check how many vat rate are applied
        vat_rate = []
        for line in self.invoice_line_ids:
            if not line.product_id:
                continue
            if len(line.tax_ids) != 1:
                raise UserError(
                    "Not support create einvoice with 2 vat rate applied to single line. Need to improve it."
                )
            vat_rate += line.tax_ids.mapped("amount")
        vat_rate = set(vat_rate)

        # support multiple vat rate -> multiple einvoice
        for vat in vat_rate:
            einvoice_line_ids = []
            for no, line in enumerate(self.invoice_line_ids, start=1):
                if not line.product_id:
                    continue
                if set(line.tax_ids.mapped("amount")) == set({vat}):
                    data = {
                        "name": line.name or line.product_id.product_einvoice_label,
                        "product_code": line.product_id.default_code,
                        "product_id": line.product_id.id,
                        "quantity": line.quantity,
                        "discount": line.discount,
                        "product_uom": line.product_uom_id.name,
                        "price_unit": line.price_unit,
                        "price_subtotal": line.price_subtotal,
                        "tax_ids": line.tax_ids.ids,
                        "line_number": no,
                    }
                    einvoice_line_ids.append([0, 0, data])
            data_to_create = {
                "partner_id": self.partner_id.id,
                "issue_date": self.invoice_date,
                "buyer_type": "individual"
                if self.partner_id.company_type == "person"
                else "company",
                "einvoice_line_ids": einvoice_line_ids,
                "account_move_ids": [],
                "vat_percent": vat,
            }
            if einvoice_template_id:
                try:
                    data_to_create["einvoice_template_id"] = einvoice_template_id.id
                except:
                    data_to_create["einvoice_template_id"] = einvoice_template_id
            einvoices.append(data_to_create)

        einvoice_ids = self.env["ntp.einvoice"].create(einvoices)
        einvoice_ids.onchange_buyer_type()
        self.write({"einvoice_ids": [[6, False, einvoice_ids.ids]]})

        for einvoice_id in einvoice_ids:
            einvoice_id.button_update_buyer_info()
            # calc price
            for line in einvoice_id.einvoice_line_ids:
                line._update_price_without_tax()
                line._update_vat_amount()

        if len(einvoice_ids) == 1:
            return {
                "name": _("EInvoices"),
                "type": "ir.actions.act_window",
                "res_model": "ntp.einvoice",
                "res_id": einvoice_ids.id,
                "views": [[False, "form"]],
                "target": "current",
            }
        else:
            return self.button_open_einvoices()

    # old ver support single invoice only
    def button_create_einvoice_old(self, einvoice_template_id=None):
        einvoice_line_ids = []
        vat_lines = []
        for line in self.invoice_line_ids:
            data = {
                "name": line.name or line.product_id.product_einvoice_label,
                "product_code": line.product_id.default_code,
                "product_id": line.product_id.id,
                "quantity": line.quantity,
                "discount": line.discount,
                "product_uom": line.product_uom_id.name,
                "price_unit": line.price_unit,
                "price_subtotal": line.price_subtotal,
                "tax_ids": line.tax_ids.ids,
            }
            vat_lines.append(line.tax_ids)
            einvoice_line_ids.append([0, 0, data])

        for tax_ids in vat_lines:
            vat_rate += tax_ids.mapped("amount")
        vat_rate = set(vat_rate)
        if len(vat_rate) != 1:
            raise UserError(f"Cannot issue EInvoice with 2 different vat: {vat_rate}")
        vat_rate = list(vat_rate)[0]
        data_to_create = {
            "partner_id": self.partner_id.id,
            "issue_date": self.invoice_date,
            "buyer_type": "individual"
            if self.partner_id.company_type == "person"
            else "company",
            "einvoice_line_ids": einvoice_line_ids,
            "account_move_ids": [],
            "vat_percent": vat_rate,
        }

        if einvoice_template_id:
            try:
                data_to_create["einvoice_template_id"] = einvoice_template_id.id
            except:
                data_to_create["einvoice_template_id"] = einvoice_template_id

        einvoice_id = self.env["ntp.einvoice"].create(data_to_create)
        einvoice_id.button_update_buyer_info()
        self.write({"einvoice_ids": [[6, False, einvoice_id.ids]]})
        # calc price
        for line in einvoice_id.einvoice_line_ids:
            line._update_price_without_tax()
            line._update_vat_amount()

        return {
            "name": _("EInvoices"),
            "type": "ir.actions.act_window",
            "res_model": "ntp.einvoice",
            "res_id": einvoice_id.id,
            "views": [[False, "form"]],
            "target": "current",
        }
