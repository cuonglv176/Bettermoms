import base64
import json
import pytz
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError
import requests
from urllib.parse import urljoin
import dateutil.parser


def parse_to_odoo_date(date_hdr):
    parsed_date = dateutil.parser.parse(date_hdr, fuzzy=True)
    if parsed_date.utcoffset() is None:
        # naive datetime, so we arbitrarily decide to make it
        # UTC, there's no better choice. Should not happen,
        # as RFC2822 requires timezone offset in Date headers.
        stored_date = parsed_date.replace(tzinfo=pytz.utc)
    else:
        stored_date = parsed_date.astimezone(tz=pytz.utc)
    return stored_date.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)


class TaxInvoice(models.Model):
    _name = "tax.invoice"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Tax Invoice"
    _order = "issued_date desc"

    # Bizzi or 3rd party info
    invoice_id = fields.Char(
        "Invoice Id",
        help="Internal Invoice Id stored in 3rd party invoice processing company",
    )
    x_company_id = fields.Char(
        "Company Id",
        help="Internal Invoice Id stored in 3rd party invoice processing company",
    )
    x_tax_invoice_valid = fields.Char("Is Tax Invoice Valid")
    x_buyer_tax_code_valid = fields.Char("Buyer Tax Code Match")
    x_buyer_legal_name_valid = fields.Char("Buyer Name Match")
    x_buyer_address_line_valid = fields.Char("Buyer Address Match")
    x_certificate_valid = fields.Char("Is Certificate Valid")
    x_digest_valid = fields.Char("Is Digest Valid")
    x_has_xml = fields.Char("Has Xml File")
    x_external_invoice_link = fields.Char(
        "Direct Link", compute="_compute_x_external_invoice_link"
    )

    received_at = fields.Date("Received Date")
    seller_address_line = fields.Char("Seller Address Line")
    seller_legal_name = fields.Char("Seller Legal Name")
    seller_tax_code = fields.Char("Seller Tax Code")
    buyer_address_line = fields.Char("Buyer Address Line")
    buyer_legal_name = fields.Char("Buyer Legal Name")
    buyer_tax_code = fields.Char("Buyer Tax Code")
    approval_status = fields.Char("Aprroval Status")
    signed_date = fields.Datetime("Signed Date")
    approved_at = fields.Datetime("Approval At")
    approved_by = fields.Char("Approval By")
    is_voided = fields.Boolean("Is Voided")

    # general info
    invoice_name = fields.Char("Invoice Name")
    template_code = fields.Char("Template Code")
    invoice_series = fields.Char("Invoice Series")
    invoice_number = fields.Char("Invoice Number", copy=False)
    payment_method_name = fields.Char("Payment Method")
    issued_date = fields.Datetime("Issued Date")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("rejected", "Rejected"),
            ("to_validate", "To Validate"),
            ("validated", "Validated"),
        ],
        "State",
        default="draft",
        copy=False,
        store=True,
        compute="_compute_state",
    )
    is_validated = fields.Boolean("Admin Validated", copy=False, default=False)
    #
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        domain="['&', ('parent_id', '=', False), '&', '|', ('company_group', '=', 'True'), ('is_company', '=', 'True'), '|', ('vat', '=', seller_tax_code), ('vat', 'like', seller_tax_code)]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.user.company_id,
    )

    # show more info for vendor and company
    vendor_vat = fields.Char("Vendor VAT", related="vendor_id.vat")
    vendor_address = fields.Char("Vendor Address", related="vendor_id.street")
    company_vat = fields.Char("Company VAT", related="company_id.vat")
    company_address = fields.Char("Company Address", related="company_id.street")
    #
    #
    currency_id = fields.Many2one("res.currency", string="Currency")
    total_amount_without_vat = fields.Monetary(
        "Total Amount Without VAT",
        # currency_field="currency"
    )
    discount_amount = fields.Monetary(
        "Discount Amount",
        # currency_field="currency"
    )
    vat_rate = fields.Integer("VAT Rate")
    vat_percent = fields.Integer("VAT Percent")
    total_vat_amount = fields.Monetary(
        "Total VAT Amount",
        # currency_field="currency"
    )
    total_amount_with_vat = fields.Monetary(
        "Total Amount With VAT",
        # currency_field="currency"
    )
    total_amount_with_vat_in_words = fields.Char("Total Amount With VAT in words")

    name = fields.Char("Invoice Full Name", compute="_compute_invoice_name", store=True)
    tax_invoice_lines = fields.One2many("tax.invoice.line", "tax_invoice_id")
    is_match_amount_invoice = fields.Boolean(
        "Is Match Amount", compute="_compute_is_match_amount_invoice", store=False
    )

    # link to account.move
    account_move_ids = fields.Many2many(
        "account.move",
        domain="['&', ('move_type','in', ['in_invoice', 'in_receipt', 'in_refund']), ('partner_id', '=', vendor_id), ('state', '!=', 'cancel')]",
    )
    account_move_count = fields.Integer(compute="_compute_account_move_count")
    account_move_total_untaxed_amount = fields.Monetary(
        compute="_compute_account_move_amount", store=False
    )
    account_move_total_taxed_amount = fields.Monetary(
        compute="_compute_account_move_amount", store=False
    )

    # to remove
    account_move_id = fields.Many2one(
        "account.move",
        domain="['&', ('move_type','in', ['in_invoice', 'in_receipt', 'in_refund']), ('partner_id', '=', vendor_id), ('state', '!=', 'cancel')]",
    )
    account_move_type = fields.Selection(
        "Account Type", related="account_move_id.move_type"
    )
    account_move_amount_untaxed = fields.Monetary(
        related="account_move_id.amount_untaxed"
    )
    account_move_amount_total = fields.Monetary(related="account_move_id.amount_total")

    # suggestion widget
    auto_created_account_move_id = fields.Integer()
    bill_receipt_suggestion_widget = fields.Text(
        compute="_compute_bill_receipt_suggestion_widget",
    )

    vendor_match_cnt = fields.Integer(
        "Vendor Match Count", compute="_compute_match_cnt", store=False
    )
    company_match_cnt = fields.Integer(
        "Company Match Count", compute="_compute_match_cnt", store=False
    )

    active = fields.Boolean("Active", default=True)

    @api.onchange("account_move_ids", "account_move_id")
    def onchange_account_move_ids(self):
        if self.account_move_id:
            self.account_move_ids = [(4, self.account_move_id.id)]
        elif not self.account_move_id:
            if self.account_move_ids:
                self.account_move_id = self.account_move_ids[0]
        self._compute_state()

    def _compute_account_move_amount(self):
        for rec in self:
            rec.account_move_total_untaxed_amount = 0
            rec.account_move_total_taxed_amount = 0
            if rec.account_move_ids:
                rec.account_move_total_untaxed_amount = sum(
                    [x.amount_untaxed for x in rec.account_move_ids]
                )
                rec.account_move_total_taxed_amount = sum(
                    [x.amount_total for x in rec.account_move_ids]
                )

    def _compute_account_move_count(self):
        for rec in self:
            rec.account_move_count = len(rec.account_move_ids)

    def _compute_x_external_invoice_link(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        bizzi_view_url = get_param("tax_invoice.tax_invoice_bizzi_view_url")
        for rec in self:
            rec.x_external_invoice_link = False
            if bizzi_view_url:
                rec.x_external_invoice_link = urljoin(
                    bizzi_view_url,
                    '/companies/%s/invoices/in?filters={"approvalStatus":["-1"]}&invoiceId=%s'
                    % (rec.x_company_id, rec.invoice_id),
                )

    def _compute_is_match_amount_invoice(self):
        for rec in self:
            rec.is_match_amount_invoice = False
            if rec.account_move_id:
                if (
                    rec.account_move_total_untaxed_amount
                    == rec.total_amount_without_vat
                    and rec.account_move_total_taxed_amount == rec.total_amount_with_vat
                ):
                    rec.is_match_amount_invoice = True

    @api.depends("template_code", "invoice_series", "invoice_number")
    def _compute_invoice_name(self):
        for rec in self:
            rec_name = "{}{}/{}".format(
                rec.template_code, rec.invoice_series, rec.invoice_number
            )
            rec.name = rec_name

    def name_get(self):
        result = []
        for record in self:
            rec_name = "{}{}/{}".format(
                record.template_code, record.invoice_series, record.invoice_number
            )
            result.append((record.id, rec_name))
        return result

    def _compute_match_cnt(self):
        for rec in self:
            vendor_match_cnt, _ = rec.get_res_partner(rec.seller_tax_code)
            company_match_cnt, _ = rec.get_company(rec.buyer_tax_code)
            rec.vendor_match_cnt = vendor_match_cnt
            rec.company_match_cnt = company_match_cnt

    def _compute_bill_receipt_suggestion_widget(self):
        for rec in self:
            rec.bill_receipt_suggestion_widget = json.dumps(False)
            if rec.account_move_id:
                # already linked, so skip suggestions
                continue
            default_invoice_date = self.get_strftime_with_user_tz(self.signed_date)
            domain = [
                "&",
                ("move_type", "in", ["in_invoice", "in_receipt", "in_refund"]),
                ("partner_id", "=", rec.vendor_id.id),
                ("currency_id", "=", rec.currency_id.id),
                # not link to any tax invoice
                # ("tax_invoice_ids", "=", False),
                # checking accounting date and signed_date must be matched - SKIP
                # ("date", "=", default_invoice_date),
                ("state", "!=", "cancel"),
            ]
            domain_vars = [
                # exact match
                [
                    ("amount_total", "=", rec.total_amount_with_vat),
                ],
                # suggest invoice in range 80 - 100% of tax invoice
                [
                    ("amount_total", "<", rec.total_amount_with_vat),
                    ("amount_total", ">", rec.total_amount_with_vat * 0.8),
                ],
                # suggest invoice in range 100 - 120% of tax invoice
                [
                    ("amount_total", "<", rec.total_amount_with_vat * 1.2),
                    ("amount_total", ">", rec.total_amount_with_vat),
                ],
            ]
            account_moves = (
                self.env["account.move"].search(domain + domain_vars[0])
                + self.env["account.move"].search(domain + domain_vars[1])
                + self.env["account.move"].search(domain + domain_vars[2])
            )
            # most 5 relevant account.move
            # account_moves_suggestion = account_moves[:5]
            account_moves_suggestion = account_moves
            bill_receipt_suggestion_widget_vals = {
                "title": _("Outstanding Bill/PR"),
                "tax_invoice_id": rec.id,
                "content": [],
            }
            for move in account_moves_suggestion:
                bill_receipt_suggestion_widget_vals["content"].append(
                    {
                        "name": move.ref or move.name,
                        "journal_name": move.journal_id.name,
                        "id": move.id,
                        "tax_invoices_count": move.tax_invoices_count,
                        "amount_total": move.amount_total,
                        "currency": move.currency_id.symbol,
                        "position": move.currency_id.position,
                        "digits": [69, move.currency_id.decimal_places],
                        "date": fields.Date.to_string(move.invoice_date),
                    }
                )
            if not bill_receipt_suggestion_widget_vals["content"]:
                continue

            rec.bill_receipt_suggestion_widget = json.dumps(
                bill_receipt_suggestion_widget_vals
            )

    def insert_log(self, message):
        self.message_post(
            body=message,
            message_type="comment",
            author_id=self.env.user.partner_id.id if self.env.user.partner_id else None,
            subtype_xmlid="mail.mt_comment",
        )

    # odoo15 check company_id field in model schema and try to get base url from it, but
    # since we already define the company_id field, so it is better to override this method
    # to get from setting
    def get_base_url(self):
        """
        Returns rooturl for a specific given record.

        By default, it return the ir.config.parameter of base_url
        but it can be overidden by model.

        :return: the base url for this record
        :rtype: string

        """
        self.ensure_one()
        return self.env["ir.config_parameter"].sudo().get_param("web.base.url")

    @api.depends("is_validated", "account_move_id")
    def _compute_state(self):
        is_rejected = lambda x: x.approval_status == "REJECTED"
        is_draft = (
            lambda x: x.account_move_id.id == False
            and x.approval_status != "REJECTED"
            and not x.is_validated
        )
        is_to_validate = (
            lambda x: x.account_move_id.id != False
            and x.approval_status != "REJECTED"
            and not x.is_validated
        )
        is_validated = (
            lambda x: x.account_move_id.id != False
            and x.approval_status != "REJECTED"
            and x.is_validated
        )
        _map = [
            (is_rejected, "rejected"),
            (is_draft, "draft"),
            (is_to_validate, "to_validate"),
            (is_validated, "validated"),
        ]
        for rec in self:
            for func, state in _map:
                if func(rec):
                    rec.state = state
                    break

    def set_validated(self):
        self.is_validated = True
        self.update_move_ref(self.account_move_ids)
        self.insert_log("Approved")

    def button_set_validated(self):
        self.ensure_one()
        if self.is_match_amount_invoice:
            self.set_validated()
        else:
            return {
                "type": "ir.actions.act_window",
                "name": "Confirm Tax Invoice Valid",
                "res_model": "tax.invoice.validate.confirm",
                "view_type": "form",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_tax_invoice_id": self.id,
                    "default_account_move_ids": self.account_move_ids.ids,
                    "default_currency_id": self.currency_id.id,
                    # vendor
                    "default_account_move_amount_untaxed": self.account_move_total_untaxed_amount,
                    "default_account_move_amount_total": self.account_move_total_taxed_amount,
                    # tax invoice
                    "default_total_amount_without_vat": self.total_amount_without_vat,
                    "default_total_amount_with_vat": self.total_amount_with_vat,
                    # diff
                    "default_difference_amount_without_vat": self.total_amount_without_vat
                    - self.account_move_total_untaxed_amount,
                    "default_difference_amount_with_vat": self.total_amount_with_vat
                    - self.account_move_total_taxed_amount,
                },
            }

    def button_set_to_validate(self):
        self.ensure_one()
        self.is_validated = False
        self.insert_log("Unapproved")

    def action_unlink_bill_or_receipt(self):
        self.ensure_one()
        self.account_move_id = False
        self.account_move_ids = False
        self.is_validated = False
        self.insert_log("Unlink to Bill/Receipt")

    def action_create_vendor_contact(self):
        self.ensure_one()
        data_to_create = {
            "name": self.seller_legal_name,
            "street": self.seller_address_line,
            "vat": self.seller_tax_code,
            "is_company": True,
        }
        partner = self.env["res.partner"].create(data_to_create)
        action = {
            "name": _("Create Vendor Contact"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "res.partner",
            "views": [[False, "form"]],
            "context": {},
            "res_id": partner.id,
            "domain": [],
            "target": "current",
        }
        return action

    def get_strftime_with_user_tz(self, date):
        tz = (
            self.env.user.tz or "Asia/Saigon"
        )  # FIXME: need to decide timezone in somewhere else
        utc_timestamp = pytz.utc.localize(date, is_dst=False)
        date_with_tz = utc_timestamp.astimezone(pytz.timezone(tz)).strftime(
            tools.DEFAULT_SERVER_DATE_FORMAT
        )
        return date_with_tz

    def _get_vat_ids(self, vat_percentage, raise_exc=True):
        try:
            # TODO: this must be consider to choose correct tax configuration, since it will be affected to accounting system
            vat_ids = self.env["account.tax"].search(
                [
                    ("amount", "=", vat_percentage),
                    ("price_include", "=", False),
                    ("type_tax_use", "=", "purchase"),
                ]
            )[0]
            return vat_ids
        except Exception as e:
            if raise_exc:
                raise UserError(
                    f"Cannot find vat = {vat_percentage} Exclude Price in 'account.tax' configuration"
                )
            return None

    def _create_bill_or_receipt(self, type):
        self.ensure_one()
        default_invoice_date = self.get_strftime_with_user_tz(self.signed_date)
        data_to_create = {
            # "currency_id": self.vendor_id.property_purchase_currency_id or self.currency_id,
            "currency_id": self.currency_id,
            "move_type": type,
            "partner_id": self.vendor_id.id,
            "ref": "{}".format(self.name),
            "invoice_date": default_invoice_date,
            "tax_invoice_ids": [(6, 0, self.ids)],
            "invoice_line_ids": [],
            "invoice_payment_term_id": self.vendor_id.property_supplier_payment_term_id,
        }

        def compute_vat(after_vat, before_vat):
            if before_vat != 0:
                vat = tools.float_round((after_vat - before_vat) / before_vat * 100, 2)
            else:
                vat = 0
            return vat

        if not self.vendor_id.is_cost_aggregation:
            for line in self.tax_invoice_lines:
                price_unit = line.unit_price or line.total_price_before_vat
                vat_percentage_compute = compute_vat(line.total_price_after_vat, line.total_price_before_vat)
                quantity = line.quantity
                if line.total_price_after_vat and quantity == 0:
                    # we have to pay but in invoice, quantity set to 0, so need to alter to 1
                    # when creating bill/receipt
                    quantity = 1
                vat_percentage = line.vat_percentage
                if (
                    vat_percentage < 0 or not vat_percentage
                ):  # some invoice comes with -1 in vat
                    vat_percentage = 0
                # fmt: off
                if vat_percentage != vat_percentage_compute:
                    self.insert_log(f"Vat Percentage For {line.item_name} ({vat_percentage}) and  Actual one computed ({vat_percentage_compute}) is different")
                    if self._get_vat_ids(vat_percentage_compute, False):
                        # re adjust vat to correct compute vat
                        self.insert_log(
                            f"Adjusted Vat When Create Invoice For {line.item_name} to ({vat_percentage_compute})"
                        )
                        vat_percentage = vat_percentage_compute
                vat_ids = self._get_vat_ids(vat_percentage)
                data_to_create["invoice_line_ids"].append(
                    (0, 0, {
                        "product_id": False, # cannot guess it
                        "name": line.item_name,
                        "quantity": quantity,
                        "price_unit": price_unit,
                        "tax_ids": [(6, 0, vat_ids.ids)],
                        'is_locked': True,
                    })
                )
                # fmt: on
        else:
            vat_percentage = self.vat_percent
            vat_percentage_compute = compute_vat(self.total_amount_with_vat, self.total_amount_without_vat)
            if (
                vat_percentage < 0 or not vat_percentage
            ):  # some invoice comes with -1 in vat
                vat_percentage = 0
            if vat_percentage != vat_percentage_compute:
                self.insert_log(
                    f"Vat Percentage In Invoice ({vat_percentage}) and  Actual one computed ({vat_percentage_compute}) is different"
                )
                if self._get_vat_ids(vat_percentage_compute, False):
                    # re adjust vat to correct compute vat
                    self.insert_log(
                        f"Adjusted Vat When Create Invoice to ({vat_percentage_compute})"
                    )
                    vat_percentage = vat_percentage_compute
            vat_ids = self._get_vat_ids(vat_percentage)
            total_amount_without_vat = self.total_amount_without_vat
            total_amount_with_vat = self.total_amount_with_vat
            product_id = self.vendor_id.aggregate_product.id
            product_name = self.vendor_id.aggregate_product.name
            account_id = self.vendor_id.aggregate_expense_account.id
            # there is 1 case when in invoice we have multiple items with different tax value
            # need to care it also
            # fmt: off
            invoice_line_ids = [(0, 0, {
                        "product_id": product_id,
                        "name": product_name,
                        "quantity": 1,
                        "price_unit": total_amount_without_vat,
                        "account_id": account_id,
                        "tax_ids": [(6, 0, vat_ids.ids)],
                        'is_locked': True
                    })]
            # fmt: on
            data_to_create["invoice_line_ids"] = invoice_line_ids

        move = (
            self.env["account.move"]
            .sudo()
            .create(data_to_create)
            .with_user(self.env.uid)
        )
        # auto find product line base on its label which are predefined
        move.button_find_product_from_label()
        return move

    def action_create_bill_or_receipt(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Cannot create bill/receipt with non-draft tax invoice")
        # TODO: need to find a way to return list view
        action_return = True if len(self) == 1 else False
        for rec in self:
            context = self.env.context.copy()
            type = context.get("type", "in_invoice")
            if type == "in_invoice":
                name = _("Create Vendor Bill")
            else:
                name = _("Create Purchase Receipt")
            move = rec._create_bill_or_receipt(type)
            rec.account_move_ids = [(4, move.id)]
            rec.account_move_id = move.id
            action = {
                "name": name,
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "account.move",
                "views": [[False, "form"]],
                "context": {},
                "res_id": move.id,
                "domain": [],
                "target": "current",
            }
            if action_return:
                return action

    def action_reject_single(self):
        self.ensure_one()
        self.set_invoice_status("reject")

    def action_unreject_single(self):
        self.ensure_one()
        self.set_invoice_status("unreject")

    def action_approve_single(self):
        self.ensure_one()
        self.set_invoice_status("approve")

    def action_unapprove_single(self):
        self.ensure_one()
        self.set_invoice_status("unapprove")

    ##############
    def set_invoice_status(self, status):
        # REJECTED / UNREJECTED / APPROVED / UNAPPROVED / PENDING
        self.ensure_one()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
        api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")
        headers = {"accept": "application/json", "X-API-KEY": api_key}
        url = urljoin(api_url, f"v1/invoices/{self.invoice_id}/{status}")
        method = None
        method = "post" if status in ["approve", "reject"] else method
        method = "delete" if status in ["unapprove", "unreject"] else method

        if status == "reject":
            json_body = {
                "reject_reasons": ["Reject From Odoo User {self.env.user.name}"]
            }
        else:
            json_body = None
        action_performable = False
        valid_pairs = [
            ("APPROVED", "unapprove"),
            ("REJECTED", "unreject"),
            ("PENDING", "approve"),
            ("PENDING", "reject"),
        ]
        if (self.approval_status, status) in valid_pairs:
            action_performable = True
        if action_performable:
            if method == "post":
                resp = requests.post(url, headers=headers, json=json_body)
            elif method == "delete":
                resp = requests.delete(url, headers=headers, json=json_body)
            else:
                raise ValueError("method is not defined")
            self.action_sync_single()
        else:
            raise UserError(f"Cannot set '{status}'. Already in this state")

    def sync_tax_invoice_type(self, api_url, api_key, invoice_io="IN"):
        url = urljoin(api_url, "v1/invoices")
        query_url = {
            "page": 1,
            "size": 20,
            "invoice_io": invoice_io,  # only get invoice we buy
            "order_by": "issued_date",
            "order_direction": "desc",
            "includes": "items,attachments,validations",
        }
        headers = {"accept": "application/json", "X-API-KEY": api_key}
        has_next_data = True
        while has_next_data:
            response = requests.get(url, params=query_url, headers=headers)
            if response.status_code == 200:
                tax_invoices_data = response.json()
                for tax_invoice in tax_invoices_data["data"]:
                    self.create_from_dict(tax_invoice)
                if tax_invoices_data["pagination"]["next"]:
                    url = urljoin(api_url, tax_invoices_data["pagination"]["next"])
                    query_url = {}
                else:
                    has_next_data = False

    def auto_create_bill_receipt(self):
        self.ensure_one()
        if not self.auto_created_account_move_id:
            vendor = self.vendor_id
            created_id = False
            if vendor.auto_create_invoice_type == "bill":
                move = self._create_bill_or_receipt("in_invoice")
                created_id = move.id
            elif vendor.auto_create_invoice_type == "receipt":
                move = self._create_bill_or_receipt("in_receipt")
                created_id = move.id
            else:
                raise ValueError(
                    f"Not support create {vendor.auto_create_invoice_type}"
                )
            self.auto_created_account_move_id = created_id
        else:
            try:
                self.env["account.move"].browse(self.auto_created_account_move_id).state
            except Exception as e:
                # schedule it for next run
                self.auto_created_account_move_id = False

    @api.model
    def _auto_create_bill_receipts(self):
        tax_invoices = self.search([("vendor_id", "!=", False)]).filtered(
            lambda x: x.state == "draft" and x.vendor_id.auto_create_invoice_enable
        )
        for ti in tax_invoices:
            ti.action_sync_single()
            ti.auto_create_bill_receipt()
        return True

    @api.model
    def sync_tax_invoice(self, *arg):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
        api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")
        # use odoobot when sync up
        self.with_user(1).sync_tax_invoice_type(
            api_url=api_url, api_key=api_key, invoice_io="IN"
        )
        self.with_user(1).sync_tax_invoice_type(
            api_url=api_url, api_key=api_key, invoice_io="UNIDENTIFIED"
        )
        res = {"type": "ir.actions.client", "tag": "reload"}
        return res

#     def action_request_verify_invoice(self):
#         get_param = self.env["ir.config_parameter"].sudo().get_param
#         api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
#         api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")
#         # FIXME: need to make param for this
#         url = "https://graphql.bizzi.services/v1/graphql"
#         for rec in self:
#             data = {
#                 "operationName": "verifyInvoice",
#                 "variables": {"invoiceId": rec.invoice_id},
#                 "query": """mutation verifyInvoice($invoiceId: uuid!) {
#     verifyInvoiceById(invoiceId: $invoiceId)
# }""",
#             }


    def action_sync_single(self):
        self.ensure_one()
        get_param = self.env["ir.config_parameter"].sudo().get_param
        api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
        api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")
        invoice_id = self.invoice_id
        url = urljoin(api_url, f"v1/invoices/{invoice_id}")
        headers = {"accept": "application/json", "X-API-KEY": api_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            invoice_data = response.json()["data"]
            self.create_from_dict(invoice_data)

    def get_res_partner(self, vat):
        # exact vat number
        partner = self.env["res.partner"].search(
            [
                "&",
                ("vat", "=", vat),
                "|",
                ("is_company", "=", True),
                ("company_group", "=", True),
            ]
        )
        if partner:
            return len(partner), partner
        # check sub vat
        partner = self.env["res.partner"].search(
            [
                "&",
                ("vat", "=like", f"{vat}-%"),
                "|",
                ("is_company", "=", True),
                ("company_group", "=", True),
            ]
        )
        if partner:
            return len(partner), partner
        return 0, None
        # need to add new ?
        raise ValueError(f"vat number {vat} has no record in db")

    def get_company(self, vat):
        # exact vat number
        company = self.env["res.company"].search([("vat", "=", vat)])
        if company:
            return len(company), company
        # check sub vat
        company = self.env["res.company"].search([("vat", "=like", f"{vat}-%")])
        if company:
            return len(company), company
        return 0, None
        # need to add new ?
        raise ValueError(f"vat number {vat} has no record in db")

    def create_from_dict(self, data):
        """
        Step by step

        Checking invoice-id existed in system
        if exists then we just update the status of invoice only

        if not exists then need to validate vendor_id and company_id to create in res.partner
        and update the tax_invoice record

        Note that we will only process IN invoice which mean invoice we pay to vendors
        not invoice we sale
        """

        invoice_id = data["invoice_id"]
        x_company_id = data["company_id"]
        approval_status = data["approval_status"]
        received_at = data["received_at"]
        invoice_name = data["invoice_name"]
        template_code = data["template_code"]
        invoice_series = data["invoice_series"]
        invoice_number = data["invoice_number"]
        payment_method_name = data["payment_method_name"]
        # 2022-02-16T17:00:00+00:00
        issued_date = parse_to_odoo_date(data["issued_date"])
        seller_address_line = data["seller_address_line"]
        seller_legal_name = data["seller_legal_name"]
        seller_tax_code = data["seller_tax_code"]
        buyer_address_line = data["buyer_address_line"]
        buyer_legal_name = data["buyer_legal_name"]
        buyer_tax_code = data["buyer_tax_code"]
        signed_date = parse_to_odoo_date(data["signed_date"])
        approved_at = (
            parse_to_odoo_date(data["approved_at"]) if data["approved_at"] else None
        )
        approved_by = data["approved_by"]
        is_voided = data["is_voided"]
        currency = data["currency"]
        vat_rate = data["vat_rate"]
        vat_percent = data["vat_percentage"]
        total_amount_without_vat = data["total_amount_without_vat"]
        total_vat_amount = data["total_vat_amount"]
        total_amount_with_vat = data["total_amount_with_vat"]
        total_amount_with_vat_in_words = data["total_amount_with_vat_in_words"]
        invoice_items = data.get("invoice_items")
        invoice_validations = data.get("validations")
        #
        attachments = data["attachments"]
        name = "{}{}/{}".format(template_code, invoice_series, invoice_number)

        domain = [
            "&",
            ("invoice_id", "=", invoice_id),
            ("x_company_id", "=", x_company_id),
        ]
        # search even with inactive entry
        tax_invoices_in_db = self.with_context(active_test=False).search(domain)
        if tax_invoices_in_db:
            rec = tax_invoices_in_db[0]
        else:
            # check seller and buyer existed
            vendor_match_cnt, vendor_id = self.get_res_partner(vat=seller_tax_code)
            company_match_cnt, company_id = self.get_company(vat=buyer_tax_code)
            # currency should always available
            currency_id = None
            try:
                # '₫' or 'đ' or 'VND' ????
                currency_id = self.env["res.currency"].search(
                    [
                        "|",
                        ("name", "=", currency),
                        ("symbol", "=", currency),
                    ]
                )[0]
            except Exception as e:
                pass
            finally:
                if not currency_id:
                    currency_id = self.env.company.currency_id
            # add new tax_invoice
            data_to_create = {
                "name": name,
                "invoice_id": invoice_id,
                "x_company_id": x_company_id,
                # "approval_status": approval_status,
                "received_at": received_at,
                "invoice_name": invoice_name,
                "template_code": template_code,
                "invoice_series": invoice_series,
                "invoice_number": invoice_number,
                "payment_method_name": payment_method_name,
                # "issued_date": issued_date,
                "seller_address_line": seller_address_line,
                "seller_legal_name": seller_legal_name,
                "seller_tax_code": seller_tax_code,
                "buyer_address_line": buyer_address_line,
                "buyer_legal_name": buyer_legal_name,
                "buyer_tax_code": buyer_tax_code,
                # "signed_date": signed_date,
                # "approved_at": approved_at,
                # "approved_by": approved_by,
                "is_voided": is_voided,
                "vat_rate": vat_rate,
                "vat_percent": vat_percent,
                "total_amount_without_vat": total_amount_without_vat,
                "total_vat_amount": total_vat_amount,
                "total_amount_with_vat": total_amount_with_vat,
                "total_amount_with_vat_in_words": total_amount_with_vat_in_words.replace(
                    "  ", " "
                ),
            }
            data_to_create.update({"currency_id": currency_id.id})
            if company_id and company_match_cnt == 1:
                data_to_create.update({"company_id": company_id.id})
            if vendor_id and vendor_match_cnt == 1:
                data_to_create.update({"vendor_id": vendor_id.id})
            rec = self.create(data_to_create)

        # update detail info for invoice
        rec.update(
            {
                "signed_date": signed_date,
                "approval_status": approval_status,
                "approved_at": approved_at,
                "approved_by": approved_by,
                "issued_date": issued_date,
                "name": name,
            }
        )

        if not rec.tax_invoice_lines and invoice_items:
            rec.process_invoice_lines(invoice_items)
        if invoice_validations:
            rec.process_validation_info(invoice_validations)
        rec.process_attachments(attachments)
        print(data)

    def process_validation_info(self, validations):
        self.ensure_one()
        # "validations": {
        # "status": "success",
        # "results": [
        #   { "key": "buyer_tax_code", "status": "success"},
        #   { "key": "buyer_legal_name", "status": "success"},
        #   { "key": "buyer_address_line", "status": "success"},
        #   { "key": "certificate", "status": "success"},
        #   { "key": "digest", "status": "success"},
        #   { "key": "has_xml", "status": "success"}
        # ]
        # }
        _to_update = {
            "x_tax_invoice_valid": validations["status"],
        }
        _map = {
            "buyer_tax_code": "x_buyer_tax_code_valid",
            "buyer_legal_name": "x_buyer_legal_name_valid",
            "buyer_address_line": "x_buyer_address_line_valid",
            "certificate": "x_certificate_valid",
            "digest": "x_digest_valid",
            "has_xml": "x_has_xml",
        }
        for check in validations["results"]:
            key = check["key"]
            status = check["status"]
            if key in _map:
                _to_update[_map[key]] = status
        self.update(_to_update)

    def process_attachments(self, attachments):
        self.ensure_one()

        records_in_db = self.env["ir.attachment"].search(
            [
                "&",
                ["res_id", "=", self.id],
                ["res_model", "=", self._name],
            ]
        )
        attached_attachments = [attach.name for attach in records_in_db]

        for attachment in attachments:
            name = attachment["name"]
            url = attachment["url"]
            filename = "{}_{}".format(self.id, name)
            if filename in attached_attachments:
                continue

            try:
                # if filename.lower().endswith(".pdf"):
                #     mimetype = "application/x-pdf"
                # elif filename.lower().endswith(".png"):
                #     mimetype = "image/png"
                # elif filename.lower().endswith(".xml"):
                #     mimetype = "application/xml"
                # else:
                #     mimetype = False
                response = requests.get(url)
                if response.status_code == 200:
                    self.env["ir.attachment"].create(
                        {
                            "name": filename,
                            "type": "binary",
                            "res_id": self.id,
                            "res_model": "tax.invoice",
                            "datas": base64.b64encode(response.content),
                            # "mimetype": mimetype,
                        }
                    )
            except Exception as e:
                pass

    def process_invoice_lines(self, invoice_items):
        self.ensure_one()
        for item in invoice_items:
            matched_items = self.env["tax.invoice.line"].search(
                [("invoice_item_id", "=", item["invoice_item_id"])]
            )
            vals_to_set = {
                "tax_invoice_id": self.id,
                "invoice_item_id": item["invoice_item_id"],
                "item_name": item["item_name"],
                "unit": item["unit"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "vat_percentage": item["vat_percentage"],
                "vat_amount": item["vat_amount"],
                "promotion": item["promotion"],
                "total_price_before_vat": item["total_price_before_vat"],
                "total_price_after_vat": item["total_price_after_vat"],
                "line_number": item["line_number"],
                "item_code": item["item_code"],
                "discount_percentage": item["discount_percentage"],
                "discount_amount": item["discount_amount"],
                "is_free": item["is_free"],
                "batch_number": item["batch_number"],
                "expire_date": item["expire_date"],
                "is_discount": item["is_discount"],
            }
            if not matched_items:
                self.env["tax.invoice.line"].create(vals_to_set)
            else:
                matched_items[0].update(vals_to_set)

    def auto_match_vendor(self):
        for rec in self:
            if not rec.vendor_id:
                vendor_match_cnt, vendor_id = rec.get_res_partner(
                    vat=rec.seller_tax_code
                )
                if vendor_match_cnt == 1:
                    rec.vendor_id = vendor_id[0]

    def sync_multi(self):
        for rec in self:
            self.create_from_invoice_id(rec.invoice_id)

    def create_from_invoice_id(self, invoice_id: str):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
        api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")
        url = urljoin(api_url, f"v1/invoices/{invoice_id}")
        headers = {"accept": "application/json", "X-API-KEY": api_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            invoice_data = response.json()["data"]
            self.create_from_dict(invoice_data)

    def js_assign_bill_receipt(self, move_id):
        self.ensure_one()
        move = self.env["account.move"].browse(move_id)
        self.update_move_ref(move)
        self.account_move_id = move
        self.account_move_ids = [(4, move.id)]
        return True

    def update_move_ref(self, account_move_ids):
        item_ref = ""
        if self.vendor_id.collect_item_code_in_bill_ref:
            item_codes = [x.item_code for x in self.tax_invoice_lines if x.item_code]
            if item_codes:
                item_ref = ', '.join(set(item_codes))
        if item_ref:
            ref = "{}, {}".format(self.name, item_ref)
        else:
            ref = "{}".format(self.name)
        for move in account_move_ids:
            if not move.ref:
                move.ref = ref
            elif move.ref and ref not in move.ref:
                move.ref = "{}, {}".format(move.ref, ref)
            else:
                pass

    def action_archive(self):
        for rec in self:
            super(TaxInvoice, rec).action_archive()
            rec.message_post(body="Set To Archive")

    def action_unarchive(self):
        for rec in self:
            super(TaxInvoice, rec).action_unarchive()
            rec.message_post(body="Set To Un-Archive")

    def button_open_linked_bill_receipt(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "views": [
                [self.env.ref("account.view_in_invoice_tree").id, "tree"],
                [self.env.ref("account.view_move_form").id, "form"],
            ],
            "domain": [["id", "in", self.account_move_ids.ids]],
            "context": {"create": False},
            "name": _("Bill/PRs"),
        }

    @api.model
    def task_copy_many2one_to_many2many(self):
        for rec in self.env["tax.invoice"].search(
            [("account_move_id", "!=", False), ("account_move_ids", "=", False)]
        ):
            rec.account_move_ids = [(4, rec.account_move_id.id)]
            rec.message_post(body="Migrated many2one to many2many invoice !!")


class TaxInvoiceLine(models.Model):
    _name = "tax.invoice.line"
    _description = "Tax Invoice Line"

    tax_invoice_id = fields.Many2one("tax.invoice", "Tax Invoice")
    currency_id = fields.Many2one(related="tax_invoice_id.currency_id")

    invoice_item_id = fields.Char(
        "Invoice Item Id"
    )  # refer: "d09c4fef-1462-489c-a204-0295275b9248",
    item_name = fields.Char("Item Name")  # refer: "Cước thuê xe khô tháng 01/2022",
    unit = fields.Char("Unit")  # refer: null,
    quantity = fields.Integer("Quantity")  # refer: 1,
    unit_price = fields.Monetary("Unit Price")  # refer: 12000000,
    vat_percentage = fields.Integer("Vat (%)")  # refer: 10,
    vat_amount = fields.Monetary("Vat Mmount")  # refer: 1200000,
    promotion = fields.Char("Promotion")  # refer: null,
    total_price_before_vat = fields.Monetary("Total Before Vat")  # refer: 12000000,
    total_price_after_vat = fields.Monetary("Total After Vat")  # refer: 13200000,
    line_number = fields.Integer("Line Number")  # refer: 1,
    item_code = fields.Char("Item Code")  # refer: null,
    discount_percentage = fields.Integer("Discount Percentage")  # refer: 0,
    discount_amount = fields.Monetary("Discount Amount")  # refer: 0,
    is_free = fields.Boolean("Is Free")  # refer: false,
    batch_number = fields.Char("Batch Number")  # refer: null,
    expire_date = fields.Date("Expire Date")  # refer: null,
    is_discount = fields.Boolean("Is Discount")  # refer: false,
