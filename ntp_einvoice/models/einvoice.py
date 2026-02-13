import logging
import base64
from io import BytesIO
import json
import re
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4
from zipfile import ZipFile
from pathlib import Path

from odoo import models, fields, api, _
from odoo.tools import float_round
from num2words import num2words
from docxtpl import DocxTemplate

from odoo.exceptions import UserError
from ..utils.const import *

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..api import EInvoiceFactory


def build_table_result(data_list: list):
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
                background-color: #009879;
                color: #ffffff;
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
                border-bottom: 2px solid #009879;
            }
        </style>

        <table class="styled-table">
        <thead>
            <tr>
                <td>Infomation</td>
                <td>Value</td>
            </tr>
        </thead>
        <tbody>
    """
    for k, v in data_list:
        data = f"""
        <tr>
            <td>{k}</td>
            <td>{v or ''}</td>
        </tr>
        """.strip()
        template += data
    template += "</tbody></table>"
    return template


class EInvoice(models.Model):
    _name = "ntp.einvoice"
    _description = "Einvoice"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, name desc"

    active = fields.Boolean("Active", default=True)

    # tmp field, because we need to understand the relationship of vat invoice first
    replace_einvoice_ids = fields.One2many(
        "ntp.einvoice",
        "replaced_by_einvoice_id",
        string="Replace",
        help="This invoice replaces other invoice",
    )
    adjust_einvoice_ids = fields.One2many(
        "ntp.einvoice",
        "adjusted_by_einvoice_id",
        string="Adjust",
        help="This invoice adjusts other invoice",
    )
    replaced_by_einvoice_id = fields.Many2one(
        "ntp.einvoice",
        string="Replaced By",
        help="This invoice is replaced by new invoice",
    )
    adjusted_by_einvoice_id = fields.Many2one(
        "ntp.einvoice",
        string="Adjusted By",
        help="This invoice is adjusted by new invoice",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.user.company_id,
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    partner_id = fields.Many2one("res.partner", "Customer")
    invoice_address = fields.Many2one(
        "res.partner",
        "Invoice Address",
        domain="[('type', '=', 'invoice'), ('parent_id', '=', partner_id)]",
    )
    einvoice_template_id = fields.Many2one("ntp.einvoice.template")
    account_move_ids = fields.Many2many("account.move", string="Ref Invoices")

    # general info
    name = fields.Char("Invoice Name", default="/", copy=False)
    number = fields.Char("Invoice Number", copy=False)
    issue_date = fields.Date(
        "Issue Date", default=lambda self: fields.Date.today(), copy=False
    )
    payment_type = fields.Selection(
        [
            (PAYMENT_TYPE_CK, "CK"),
            (PAYMENT_TYPE_TM, "TM"),
            (PAYMENT_TYPE_TM_CK, "TM/CK"),
            (PAYMENT_TYPE_DTCN, "DTCN"),
            (PAYMENT_TYPE_OTHER, "OTHER"),
        ],
        string="Payment Type",
        default=PAYMENT_TYPE_TM_CK,
    )
    payment_status = fields.Selection(
        [
            (PAYMENT_STATUS_NOT_PAID_YET, "Not Paid Yet"),
            (PAYMENT_STATUS_PAID, "Paid"),
        ],
        string="Payment Status",
        default=PAYMENT_STATUS_NOT_PAID_YET,
        copy=False,
    )
    # only applicable for new invoice created by UI, synced invoice will be get from api (not sure they will return it)
    transaction_uuid = fields.Char("Transaction UUID")

    # seller information
    seller_name = fields.Char(
        "Seller Name", default=lambda self: self.env.user.company_id.einvoice_legal_name
    )
    seller_tax_code = fields.Char(
        "Seller Tax Code", default=lambda self: self.env.user.company_id.vat
    )
    seller_address = fields.Char(
        "Seller Address", default=lambda self: self.env.user.company_id.einvoice_address
    )
    seller_phone_number = fields.Char(
        "Seller Phone",
        default=lambda self: self.env.user.company_id.einvoice_phone_number,
    )
    seller_email = fields.Char(
        "Seller Email", default=lambda self: self.env.user.company_id.einvoice_email
    )
    seller_code = fields.Char("Seller Code")
    seller_bank_name = fields.Char(
        "Seller Bank Name", default=lambda self: self.env.user.company_id.einvoice_bank
    )
    seller_bank_account = fields.Char(
        "Seller Bank Account",
        default=lambda self: self.env.user.company_id.einvoice_bank_account,
    )
    seller_website = fields.Char(
        "Seller Website", default=lambda self: self.env.user.company_id.einvoice_website
    )

    # buyer information
    buyer_name = fields.Char("Buyer Name")
    buyer_company_name = fields.Char("Buyer Company Name")
    buyer_tax_code = fields.Char("Buyer Tax Code")
    buyer_address = fields.Char("Buyer Address")
    buyer_code = fields.Char("Buyer Code")
    buyer_phone_number = fields.Char("Buyer Phone")
    buyer_email = fields.Char("Buyer Email")
    buyer_bank_name = fields.Char("Buyer Bank Name")
    buyer_bank_account = fields.Char("Buyer Bank Account")
    buyer_note = fields.Text("Buyer Note")
    # individual -> disable buyer_company_name
    buyer_type = fields.Selection(
        [
            (BUYER_NOT_NEED_INVOICE, "User Not Need Invoice"),
            (BUYER_INDIVIDUAL, "Individual"),
            (BUYER_COMPANY, "Company"),
        ],
        default=BUYER_NOT_NEED_INVOICE,
    )

    # items info
    einvoice_line_ids = fields.One2many("ntp.einvoice.line", "einvoice_id")

    # aggr data from einvoice lines
    total_amount_without_vat = fields.Monetary(
        "Total Amount Without VAT", compute="_compute_invoice_info", store=True
    )
    discount_amount = fields.Monetary(
        "Discount Amount", compute="_compute_invoice_info", store=True
    )
    vat_percent = fields.Float("VAT (%)", default=8)
    total_vat_amount = fields.Monetary(
        "Total VAT Amount", compute="_compute_invoice_info", store=True
    )
    total_amount_with_vat = fields.Monetary(
        "Total Amount With VAT", compute="_compute_invoice_info", store=True
    )
    total_amount_with_vat_in_words = fields.Char(
        "Total Amount With VAT in words", compute="_compute_invoice_info", store=True
    )

    # external information belong to provider of invoice like sinvoice/einvoice/fptinvoice...
    x_invoice_data = fields.Text(copy=False)
    x_provider_last_sync_time = fields.Datetime(copy=False)
    x_provider_data = fields.Text(copy=False)
    x_provider_last_error = fields.Text(copy=False)
    x_provider_xml_file = fields.Many2one(
        "ir.attachment", compute="_compute_x_provider_xml_file"
    )
    x_provider_display_data = fields.Text("Provider Dynamic Data")
    x_provider_request_mccqt = fields.Boolean(
        "Request MCCQT",
        default=False,
        store=True,
        compute="_compute_x_provider_request_mccqt",
        help="Indicate that einvoice is requesting MCCQT",
    )
    x_provider_mccqt = fields.Text(
        "MCCQT", help="Code that Tax Authorities Provide For Valid E-Invoice"
    )
    x_is_product_id_filled = fields.Boolean(compute="_compute_x_is_product_id_filled")
    x_invoice_note = fields.Char(compute="_compute_x_invoice_note", store=True)
    x_can_change_einvoice_no = fields.Boolean(
        compute="compute_x_can_change_einvoice_no", store=False
    )
    x_invoice_address_confirm = fields.Boolean("Address Confirm ?", default=False)

    # provider einvoice status
    provider_einvoice_status = fields.Selection(
        [
            (PROVIDER_EINVOICE_STATUS_DRAFT, "Draft"),
            (PROVIDER_EINVOICE_STATUS_REQUESTED, "Requested"),
            (PROVIDER_EINVOICE_STATUS_ISSUED, "Issued"),
            (PROVIDER_EINVOICE_STATUS_REPLACE, "Replace Other"),
            (PROVIDER_EINVOICE_STATUS_BE_REPLACED, "Be Replaced"),
            (PROVIDER_EINVOICE_STATUS_ADJUST, "Adjust Other"),
            (PROVIDER_EINVOICE_STATUS_BE_ADJUSTED, "Be Adjusted"),
            (PROVIDER_EINVOICE_STATUS_CANCELED, "Canceled"),
            (PROVIDER_EINVOICE_STATUS_UNKNOWN, "Unknown"),
        ],
        "EInvoice Status",
        default="draft",
        copy=False,
    )
    # internal odoo state
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_validate", "To Validate"),
            ("validated", "Validated"),
        ],
        "State",
        store=False,
        compute="_compute_state",
        default="draft",
    )
    is_validated = fields.Boolean(copy=False)

    @api.depends("x_provider_mccqt")
    def _compute_x_provider_request_mccqt(self):
        for rec in self:
            if rec.x_provider_mccqt:
                rec.x_provider_request_mccqt = True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if (
                not record.transaction_uuid
                and record.provider_einvoice_status == PROVIDER_EINVOICE_STATUS_DRAFT
            ):
                record.transaction_uuid = str(uuid4())
        return records

    def compute_x_can_change_einvoice_no(self):
        for rec in self:
            rec.x_can_change_einvoice_no = False
            # sometimes we cannot get invoice no, right after invoice is created -> allow user to edit it
            if (
                rec.name == "/" or not rec.name
            ) and rec.provider_einvoice_status == PROVIDER_EINVOICE_STATUS_REQUESTED:
                rec.x_can_change_einvoice_no = True

    def _compute_x_invoice_note(self):
        for rec in self:
            rec.x_invoice_note = ""
            for line in rec.einvoice_line_ids:
                if line.line_type != "1":
                    # ! FIXME: avoid this hard code here
                    if line.name and (
                        "khuyến mãi" in line.name.lower()
                        or "biếu tặng" in line.name.lower()
                        or "hàng tặng" in line.name.lower()
                    ):
                        rec.x_invoice_note = "Promotion"
                        break
                    if line.name and "bảo hành" in line.name.lower():
                        rec.x_invoice_note = "Warranty"
                        break

    def _compute_x_is_product_id_filled(self):
        for rec in self:
            x_is_product_id_filled = True
            for line in rec.einvoice_line_ids:
                if not line.product_id and line.x_is_product_line:
                    x_is_product_id_filled = False
                    break
            rec.x_is_product_id_filled = x_is_product_id_filled

    def _compute_x_provider_xml_file(self):
        for rec in self:
            rec.x_provider_xml_file = False
            attachments = self.env["ir.attachment"].search(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )
            for attachment in attachments:
                if attachment.name.endswith(".xml") or attachment.name.endswith(".zip"):
                    rec.x_provider_xml_file = attachment.id

    def _get_factory_db(self) -> Dict[int, "EInvoiceFactory"]:
        """this method is only used when you need to perform some single action for just single invoice
        In case batch operation, need to
        """
        # To avoid circular import when odoo init
        from ..api import EInvoiceFactory

        factory_db = {}
        for rec in self:
            if rec.einvoice_template_id.id not in factory_db:
                factory_db[rec.einvoice_template_id.id] = EInvoiceFactory.from_provider(
                    rec.einvoice_template_id
                )
        return factory_db

    def name_get(self):
        result = []
        for record in self:
            if record.provider_einvoice_status == "draft" and record.name == "/":
                rec_name = "Draft (*{})".format(record.id)
                result.append((record.id, rec_name))
            else:
                result.append((record.id, record.name))
        return result

    def _compute_state(self):
        for rec in self:
            rec.state = "draft"
            if rec.is_validated:
                rec.state = "validated"
            elif rec.account_move_ids:
                rec.state = "to_validate"

    @api.onchange("vat_percent")
    def _update_einvoice_line(self):
        for line in self.einvoice_line_ids:
            line._update_vat_amount()

    @api.depends(
        "provider_einvoice_status",
        "einvoice_line_ids.quantity",
        "einvoice_line_ids.discount",
        "einvoice_line_ids.product_id",
        "einvoice_line_ids.vat_amount",
        "einvoice_line_ids.price_subtotal",
        "einvoice_line_ids.price_total",
    )
    def _compute_invoice_info(self):
        for rec in self:
            rounding_issue = False
            total_amount_without_vat = 0
            total_vat_amount = 0
            total_amount_with_vat = 0
            discount_amount = 0

            # check up invoice is cancelled then set all is 0
            if rec.provider_einvoice_status == PROVIDER_EINVOICE_STATUS_CANCELED:
                rec.total_amount_without_vat = 0
                rec.total_vat_amount = 0
                rec.total_amount_with_vat = 0
                rec.discount_amount = 0
                rec.total_amount_with_vat_in_words = "Không đồng."
                continue

            for line in rec.einvoice_line_ids:
                total_amount_without_vat += line.price_subtotal
                total_vat_amount += line.vat_amount
            total_amount_with_vat = total_amount_without_vat + total_vat_amount

            # readjust base on original odoo invoice
            if len(rec.account_move_ids) == 1:
                tax_totals_json = json.loads(rec.account_move_ids.tax_totals_json)
                for untaxed_amount_group_by_tax in tax_totals_json[
                    "groups_by_subtotal"
                ]["Untaxed Amount"]:
                    # checking vat matches
                    try:
                        # finding taxed amount in origin invoice -> take it here to compare vat
                        if (
                            float(
                                "".join(
                                    re.findall(
                                        "\d+",
                                        untaxed_amount_group_by_tax["tax_group_name"],
                                    )
                                )
                            )
                            == rec.vat_percent
                        ):
                            amount_total = (
                                untaxed_amount_group_by_tax["tax_group_amount"]
                                + untaxed_amount_group_by_tax["tax_group_base_amount"]
                            )
                            amount_untaxed = untaxed_amount_group_by_tax[
                                "tax_group_base_amount"
                            ]
                            # we do adjustment if data is from rounding issue
                            if (
                                abs(amount_total - total_amount_with_vat) == 0
                                and abs(amount_untaxed - total_vat_amount) == 0
                            ):
                                # perfect matched, do nothing
                                pass
                            elif (
                                abs(amount_total - total_amount_with_vat) <= 5
                                or abs(amount_untaxed - total_vat_amount) <= 5
                            ):
                                total_amount_with_vat = amount_total
                                total_amount_without_vat = amount_untaxed
                                total_vat_amount = amount_total - amount_untaxed
                                rounding_issue = True
                    except:
                        pass

            if (
                total_amount_without_vat,
                total_vat_amount,
                total_amount_with_vat,
                discount_amount,
            ) != (
                rec.total_amount_without_vat,
                rec.total_vat_amount,
                rec.total_amount_with_vat,
                rec.discount_amount,
            ):
                rec.total_amount_without_vat = total_amount_without_vat
                rec.total_vat_amount = total_vat_amount
                rec.total_amount_with_vat = total_amount_with_vat
                rec.discount_amount = discount_amount
                if rounding_issue:
                    rec.message_post(
                        body=f"rounding issue. follow data from invoice {rec.account_move_ids.name}"
                    )

            if rec.total_amount_with_vat:
                try:
                    rec.total_amount_with_vat_in_words = (
                        num2words(
                            int(rec.total_amount_with_vat), lang="vi_VN"
                        ).capitalize()
                        + " đồng."
                    )
                except NotImplementedError:
                    rec.total_amount_with_vat_in_words = (
                        num2words(
                            int(rec.total_amount_with_vat), lang="en"
                        ).capitalize()
                        + " VND."
                    )
                except Exception as e:
                    rec.message_post(
                        body=f"cannot generate total_amount_with_vat_in_words for total_amount_with_vat={rec.total_amount_with_vat}"
                    )

    def button_update_invoice_line_label(self):
        for rec in self:
            for line in rec.einvoice_line_ids:
                line._update_product_label()
                line._update_product_uom()

    def button_update_invoice_info(self):
        self._compute_invoice_info()

    def button_update_buyer_info(self):
        data = {
            "buyer_name": False,
            "buyer_company_name": False,
            "buyer_tax_code": False,
            "buyer_address": False,
            "buyer_code": False,
            "buyer_phone_number": False,
            "buyer_email": False,
            "buyer_bank_name": False,
            "buyer_bank_account": False,
        }
        if self.partner_id:
            if self.buyer_type == "individual":
                #  in case of individual, company name and tax code must be set empty
                data["buyer_name"] = self.partner_id.name
                data["buyer_company_name"] = ""
                data["buyer_tax_code"] = ""
                data["buyer_address"] = self.partner_id.street or ""
                data["buyer_phone_number"] = self.partner_id.phone or ""
                data["buyer_email"] = self.partner_id.email or ""
                data["buyer_code"] = self.partner_id.company_group_code.name or ""
                self.update(data)
            elif self.buyer_type == "company":
                data["buyer_name"] = self.partner_id.name
                data["buyer_company_name"] = self.partner_id.legal_name
                data["buyer_tax_code"] = self.partner_id.vat
                data["buyer_address"] = self.partner_id.street or ""
                data["buyer_phone_number"] = self.partner_id.phone or ""
                data["buyer_email"] = self.partner_id.email or ""
                data["buyer_code"] = self.partner_id.company_group_code.name or ""
                if self.partner_id.child_ids:
                    buyer_name = None
                    street = None
                    # update correct street name and buyer_name from invoice sub contact of this partner
                    for child in self.partner_id.child_ids:
                        if child.type == "invoice":
                            if child.name:
                                buyer_name = child.name
                            if child.street:
                                street = child.street
                            if buyer_name and street:
                                break
                    if buyer_name:
                        data["buyer_name"] = buyer_name
                    if street:
                        data["buyer_address"] = street
                # in case invoice address are set
                if self.invoice_address:
                    data["buyer_name"] = self.invoice_address.name
                    data["buyer_address"] = self.invoice_address.street
                    data["buyer_phone_number"] = self.invoice_address.phone
                    data["buyer_email"] = self.invoice_address.email
                data = {k: v for k, v in data.items() if v != False}
                self.update(data)
            elif self.buyer_type == "unidentified":
                self.update(data)
                self.buyer_name = "Người mua không lấy hóa đơn"
                self.buyer_address = "./."
            else:
                raise UserError(f"Not support this buyer_type = {self.buyer_type}")
        else:
            raise UserError("Please choose Customer first")

    def button_send_tax_authority(self):
        factory_db = self._get_factory_db()
        for rec in self:
            try:
                factory = factory_db[rec.einvoice_template_id.id]
                factory.send_tax_authority(rec)
                rec.x_provider_request_mccqt = True
            except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
                raise UserError(str(e))

    def button_gen_agreement_doc_vat(self):
        def cast2int(val):
            if int(val) == val:
                return int(val)
            return val

        def generate_common(einvoice: EInvoice) -> dict:
            return {
                "name": einvoice.name,
                "number": einvoice.name.replace(
                    einvoice.einvoice_template_id.invoice_series, ""
                ),
                "type": einvoice.einvoice_template_id.invoice_template_type,
                "series": einvoice.einvoice_template_id.invoice_series,
                "issue": {
                    "day": einvoice.issue_date.day,
                    "month": einvoice.issue_date.month,
                    "year": einvoice.issue_date.year,
                },
            }

        def generate_items(einvoice: EInvoice) -> List:
            items = []
            for item in einvoice.einvoice_line_ids:
                items.append(
                    {
                        "id": item.line_number,
                        "description": item.name,
                        "unit": item.product_uom,
                        "quantity": cast2int(item.quantity),
                        "unit_price": cast2int(item.price_unit_without_tax),
                        "amount": cast2int(item.price_subtotal),
                    }
                )
            return items

        def generate_summary(einvoice: EInvoice) -> List:
            return {
                "total_amount": cast2int(einvoice.total_amount_without_vat),
                "vat_percent": cast2int(einvoice.vat_percent),
                "vat_amount": cast2int(einvoice.total_vat_amount),
                "total_payment": cast2int(einvoice.total_amount_with_vat),
                "total_payment_in_words": einvoice.total_amount_with_vat_in_words,
            }

        self.ensure_one()
        if not self.adjust_einvoice_ids:
            raise UserError(
                "Cannot generate agreement. this invoice not adjust other invoice !!"
            )
        be_adjusted_invoice: "EInvoice" = self.adjust_einvoice_ids[0]
        adjust_invoice = self
        data = {
            "partner": {
                "name": adjust_invoice.buyer_name or "",
                "head": adjust_invoice.buyer_company_name or "",
                "address": adjust_invoice.buyer_address or "",
                "phone": adjust_invoice.buyer_phone_number or "",
                "vat": adjust_invoice.buyer_tax_code or "",
                "email": adjust_invoice.buyer_email or "",
            },
            "be_adjusted_invoice": generate_common(be_adjusted_invoice),
            "adjust_invoice": generate_common(adjust_invoice),
        }
        # be adjusted and adjust invoice info are the same, only diff are vat
        data["be_adjusted_invoice"]["items"] = generate_items(be_adjusted_invoice)
        data["adjust_invoice"]["items"] = generate_items(be_adjusted_invoice)
        # since only vat are changed and in the adjust invoice will not have full info of be adjusted invoice
        # so just copy be adjusted invoice and then add the vat change into the data
        data["be_adjusted_invoice"]["summary"] = generate_summary(be_adjusted_invoice)
        data["adjust_invoice"]["summary"] = generate_summary(be_adjusted_invoice)
        # add up vat
        data["adjust_invoice"]["summary"]["vat_amount"] = cast2int(
            float_round(
                be_adjusted_invoice.total_amount_without_vat
                * adjust_invoice.vat_percent
                / 100, 0
            )
        )
        data["adjust_invoice"]["summary"]["vat_percent"] = cast2int(
            adjust_invoice.vat_percent
        )
        data["adjust_invoice"]["summary"]["total_payment"] = cast2int(
            be_adjusted_invoice.total_amount_without_vat
            + data["adjust_invoice"]["summary"]["vat_amount"]
        )
        data["adjust_invoice"]["summary"]["total_payment_in_words"] = (
            num2words(
                int(data["adjust_invoice"]["summary"]["total_payment"]), lang="vi_VN"
            ).capitalize()
            + " đồng."
        )

        # beautify number to show
        def prettify_number2string(num):
            format_str = "{:_}"
            return format_str.format(num).replace(".", ",").replace("_", ".")

        def prettify_number2string_all(data: dict):
            data["adjust_invoice"]["summary"]["total_amount"] = prettify_number2string(data["adjust_invoice"]["summary"]["total_amount"])
            data["adjust_invoice"]["summary"]["total_payment"] = prettify_number2string(data["adjust_invoice"]["summary"]["total_payment"])
            data["adjust_invoice"]["summary"]["vat_amount"] = prettify_number2string(data["adjust_invoice"]["summary"]["vat_amount"])
            data["be_adjusted_invoice"]["summary"]["total_amount"] = prettify_number2string(data["be_adjusted_invoice"]["summary"]["total_amount"])
            data["be_adjusted_invoice"]["summary"]["total_payment"] = prettify_number2string(data["be_adjusted_invoice"]["summary"]["total_payment"])
            data["be_adjusted_invoice"]["summary"]["vat_amount"] = prettify_number2string(data["be_adjusted_invoice"]["summary"]["vat_amount"])
            for item in data["adjust_invoice"]["items"]:
                item["unit_price"] = prettify_number2string(item["unit_price"])
                item["amount"] = prettify_number2string(item["amount"])
            for item in data["be_adjusted_invoice"]["items"]:
                item["unit_price"] = prettify_number2string(item["unit_price"])
                item["amount"] = prettify_number2string(item["amount"])
            return data
        data = prettify_number2string_all(data)

        tpl = DocxTemplate(
            Path(__file__).resolve().parent.parent
            / "static"
            / "template"
            / "Bien_ban_dieu_chinh_hoa_don_template.docx"
        )
        tpl.render(data)
        doc_name = f"Bien_ban_dieu_chinh_hoa_don_{adjust_invoice.name}_cho_{be_adjusted_invoice.name}.docx"
        from io import BytesIO

        doc = BytesIO()
        doc.read()
        tpl.save(doc)
        doc.seek(0)  # reset to let read all again
        doc_data = doc.getvalue()

        # delete all xml with same name first
        self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("name", "=", doc_name),
            ]
        ).unlink()
        ir_attachment_id = self.env["ir.attachment"].create(
            {
                "name": doc_name,
                "type": "binary",
                "datas": base64.b64encode(doc_data),
                "store_fname": doc_name,
                "res_model": self._name,
                "res_id": self.id,
            }
        )

    @api.depends("buyer_type")
    def _onchange_buyer_type(self):
        if self.buyer_type == "unidentified":
            self.button_update_buyer_info()

    def _check_invoice_valid_to_issue(self):
        self.ensure_one()
        if self.buyer_type == "company" and (
            not self.buyer_tax_code or not self.buyer_company_name
        ):
            self.message_post(
                body="<b>_check_invoice_valid_to_issue = False</b>: Invoice issue to company must have tax_code and company_name"
            )
            return False
        return True

    def _prepare_invoice_data(self):
        self.ensure_one()
        for line in self.einvoice_line_ids:
            line._update_vat_amount()

    def _update_provider_data(self, data):
        self.ensure_one()
        if self.x_provider_data == False:
            x_provider_data = {}
        else:
            x_provider_data = json.loads(self.x_provider_data)
        x_provider_data.update(**data)
        self.x_provider_data = json.dumps(x_provider_data)

    def button_preview_einvoice(self):
        self.ensure_one()
        self._prepare_invoice_data()
        context = {
            "default_einvoice_id": self.id,
        }
        if self.einvoice_template_id:
            context["default_einvoice_template_id"] = self.einvoice_template_id.id
        preview_wizsard = self.env["ntp.einvoice.preview"].create(
            {
                "einvoice_id": self.id,
                "einvoice_template_id": self.einvoice_template_id.id,
            }
        )
        preview_wizsard.button_preview()

        return {
            "type": "ir.actions.act_window",
            "name": "Preview EInvoice Before Create It",
            "res_model": "ntp.einvoice.preview",
            "res_id": preview_wizsard.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            # "context": context,
        }

    def button_manual_set_einvoice(self):
        self.ensure_one()
        self._prepare_invoice_data()
        context = {
            "default_einvoice_id": self.id,
        }
        if self.einvoice_template_id:
            context["default_einvoice_template_id"] = self.einvoice_template_id.id
        manual_wizsard = self.env["ntp.einvoice.manual.set.invoice.no"].create(
            {
                "einvoice_id": self.id,
                "einvoice_template_id": self.einvoice_template_id.id,
            }
        )
        manual_wizsard.button_try_to_find_invoice_no()

        return {
            "type": "ir.actions.act_window",
            "name": "Manual Set E-Invoice Number",
            "res_model": "ntp.einvoice.manual.set.invoice.no",
            "res_id": manual_wizsard.id,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            # "context": context,
        }

    def button_cancel_invoice(self):
        factory_db = self._get_factory_db()
        for rec in self:
            try:
                factory = factory_db[rec.einvoice_template_id.id]
                factory.cancel_invoice(rec)
                rec.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_CANCELED
            except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
                raise UserError(str(e))

    @api.onchange("buyer_type")
    def onchange_buyer_type(self):
        for rec in self:
            rec.x_invoice_address_confirm = True
            # alway revalidate when change to company
            if rec.buyer_type == "company":
                rec.x_invoice_address_confirm = False

    def button_confirm_address(self):
        if not self.x_invoice_address_confirm:
            if self.partner_id:
                action = self.partner_id.button_find_mst()
                action["context"]["default_einvoice_id"] = self.id
                action["res_model"] = "mst.vn.finder.wizard.address.confirm"
                return action
            else:
                raise UserError("Need to Select Customer")

    def button_issue_einvoice(self):
        # FIXME: issue invoice multiple time is not effective, since provider may refuse it
        factory_db = self._get_factory_db()
        for rec in self:
            if not rec._check_invoice_valid_to_issue():
                continue
            if not rec.x_invoice_address_confirm:
                raise UserError(
                    "Cannot issue invoice which not confirm address yet. Click `Confirm Address` button to proceed !"
                )
            rec._prepare_invoice_data()
            factory = factory_db[self.einvoice_template_id.id]
            try:
                res = factory.create_invoice(self)
            except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
                raise UserError(str(e))
            if res:
                rec.name = res["invoice_no"]
                rec.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_REQUESTED
                rec._update_provider_data(res["provider_data"])
            else:
                raise UserError(
                    f"""
                Cannot create einvoice. Response from server:

                {res}
                """.strip()
                )

    def button_update_invoice_status(self):
        """need to use wizard here to reduce list of button shown on UI"""
        context = {"default_einvoice_id": self.id}
        return {
            "type": "ir.actions.act_window",
            "name": "Update EInvoice Invoice Before Create It",
            "res_model": "ntp.einvoice.sync.from.odoo",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def button_sync_provider_data(self):
        """return a wizard to sync up pdf, xml data and other info"""
        context = {"default_einvoice_id": self.id}
        return {
            "type": "ir.actions.act_window",
            "name": "Update EInvoice Invoice Before Create It",
            "res_model": "ntp.einvoice.sync.from.provider",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def button_set_invoice_paid(self):
        factory_db = self._get_factory_db()
        for rec in self:
            factory = factory_db[rec.einvoice_template_id.id]
            try:
                factory.set_invoice_paid(rec)
                rec.payment_status = PAYMENT_STATUS_PAID
            except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
                raise UserError(str(e))

    def button_set_invoice_unpaid(self):
        factory_db = self._get_factory_db()
        for rec in self:
            factory = factory_db[rec.einvoice_template_id.id]
            try:
                factory.set_invoice_unpaid(rec)
                rec.payment_status = PAYMENT_STATUS_PAID
            except factory.FEATURE_NOT_SUPPORT_EXCEPTION as e:
                raise UserError(str(e))

    def _get_xml_bs(self):
        self.ensure_one()
        xml_data = None
        if self.x_provider_xml_file.name.endswith(".zip"):
            zipf = ZipFile(
                BytesIO(base64.b64decode(self.x_provider_xml_file.datas)), "r"
            )
            for zinfo in zipf.filelist:
                # sinvoice v1
                if zinfo.filename.endswith("xml"):
                    xml_data = zipf.read(zinfo)
                elif zinfo.filename.endswith("zip"):
                    # sinvoice v2
                    zipf_zip = ZipFile(BytesIO(zipf.read(zinfo)), "r")
                    xml_zinfo = [
                        zinfo_sub
                        for zinfo_sub in zipf_zip.filelist
                        if zinfo_sub.filename.endswith("xml")
                    ]
                    if xml_zinfo:
                        xml_data = zipf_zip.read(xml_zinfo[0])
        elif self.x_provider_xml_file.name.endswith(".xml"):
            xml_data = self.x_provider_xml_file.datas
        return xml_data

    def button_update_detail_from_xml(self, force_recreate_lines=False):
        from ..utils.read_vat_invoice_xml import VatEInvoiceReader

        for rec in self:
            try:
                xml_data = rec._get_xml_bs()
                reader = VatEInvoiceReader(xml_data=xml_data)
                # to update
                rec.__update_general_info(reader.get_general_info())
                rec.__update_seller_info(reader.get_seller_info())
                rec.__update_buyer_info(reader.get_buyer_info())
                if force_recreate_lines:
                    rec.einvoice_line_ids.unlink()
                rec.__update_item_info(reader.get_item_info())
                rec.__update_x_provider_display_data(reader.get_dynamic_provider_data())
                rec._compute_x_invoice_note()
                # update related invoice
                rec.__update_related_invoice_data(reader.get_related_invoice())
                # update mccqt code
                rec.x_provider_mccqt = reader.get_mccqt()
                # update customer
                rec.button_find_customer_and_address()
                rec.message_post(body=f"Updated Ok.")
            except Exception as e:
                rec.message_post(body=f"Error When Update from xml, {e}")

    def button_find_customer_and_address(self):
        for rec in self:
            if not rec.partner_id:
                # find by tax code
                if rec.buyer_tax_code:
                    rec.partner_id = rec._get_res_partner(rec.buyer_tax_code)

    def __update_related_invoice_data(
        self, related_invoice_data: Optional[dict] = None
    ):
        if not related_invoice_data:
            return
        self.ensure_one()
        try:
            invoice_name = "{}{}".format(
                related_invoice_data["invoice_series"],
                related_invoice_data["invoice_no"],
            )
            invoice = (
                self.env["ntp.einvoice"]
                .with_context(active_test=False)
                .search([("name", "=", invoice_name)])
            )
            if (
                invoice
                and related_invoice_data["invoice_properties"]
                == THIS_EINVOICE_BE_REPLACED_BY_OTHER_EINVOICE
            ):
                invoice.replaced_by_einvoice_id = self
                self.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_REPLACE
                invoice.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_BE_REPLACED
            elif (
                invoice
                and related_invoice_data["invoice_properties"]
                == THIS_EINVOICE_BE_ADJUSTED_BY_OTHER_EINVOICE
            ):
                invoice.adjusted_by_einvoice_id = self
                self.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_ADJUST
                invoice.provider_einvoice_status = PROVIDER_EINVOICE_STATUS_BE_ADJUSTED
            else:
                pass
        except Exception as e:
            logger.error(e, exc_info=True)

    def task_download_missing_attachments(self):
        run_per_cycle = 20
        run_cnt = 0
        einvoices: List["EInvoice"] = (
            self.env["ntp.einvoice"]
            .with_context(active_test=False)
            .sudo()
            .search([("provider_einvoice_status", "!=", "draft")])
        )
        factory_db = einvoices._get_factory_db()
        for rec in einvoices:
            attachment_names = (
                self.env["ir.attachment"]
                .search([("res_model", "=", "ntp.einvoice"), ("res_id", "=", rec.id)])
                .mapped("name")
            )
            pdf_donwloaded = any([x.endswith("pdf") for x in attachment_names])
            xml_donwloaded = any(
                [x.endswith("zip") or x.endswith("xml") for x in attachment_names]
            )
            if not pdf_donwloaded or not xml_donwloaded:
                # counter to run
                run_cnt += 1
            else:
                continue
            if run_cnt >= run_per_cycle:
                # we stop run to keep odoo functional in UI
                logger.info("Reach maximum run per cycle, wait for next cycle")
                break
            factory = factory_db[rec.einvoice_template_id.id]
            res_pdf = res_xml = None
            logger.info(f"Downloading attachment for einvoice: {rec.name}")
            if not pdf_donwloaded:
                res_pdf = factory.get_invoice_attachment_pdf(rec)
            if not xml_donwloaded:
                res_xml = factory.get_invoice_attachment_xml(rec)
            rec.message_post(
                body="Donwloaded attachments from server by scheduled task"
            )
            if res_pdf:
                # delete all pdf with same name first
                self.env["ir.attachment"].search(
                    [
                        ("res_model", "=", rec._name),
                        ("res_id", "=", rec.id),
                        ("name", "=", res_pdf["file_name"]),
                    ]
                ).unlink()
                self.env["ir.attachment"].create(
                    {
                        "name": res_pdf["file_name"],
                        "type": "binary",
                        "datas": res_pdf["file_data"],
                        "store_fname": res_pdf["file_name"],
                        "res_model": rec._name,
                        "res_id": rec.id,
                    }
                )
            if res_xml:
                # delete all xml with same name first
                self.env["ir.attachment"].search(
                    [
                        ("res_model", "=", rec._name),
                        ("res_id", "=", rec.id),
                        ("name", "=", res_xml["file_name"]),
                    ]
                ).unlink()
                self.env["ir.attachment"].create(
                    {
                        "name": res_xml["file_name"],
                        "type": "binary",
                        "datas": res_xml["file_data"],
                        "store_fname": res_xml["file_name"],
                        "res_model": rec._name,
                        "res_id": rec.id,
                    }
                )

    @api.model
    def _get_res_partner(self, vat):
        # exact vat number
        partner = self.env["res.partner"].search(
            ["&", ("vat", "=", vat), ("is_company", "=", True)],
        )
        if len(partner) == 1 and partner:
            return partner.id
        # check sub vat
        partner = self.env["res.partner"].search(
            ["&", ("vat", "=like", f"{vat}-%"), ("is_company", "=", True)]
        )
        if len(partner) == 1 and partner:
            return partner.id
        partner = self.env["res.partner"].search(
            [
                "&",
                ("vat", "=", vat),
                ("company_group", "=", True),
                ("parent_id", "=", False),
            ],
        )
        if len(partner) == 1 and partner:
            return partner.id
        return False

    def __update_general_info(self, data: dict):
        map_ = {
            # "currency": "currency",
            # "payment_method": "payment_method",
            # "invoice_template_type": "invoice_template_type",
            # "invoice_series": "invoice_series",
            # "invoice_id": "invoice_id",
            "issue_date": "issue_date",
            # "payment_status": "payment_status",
            # "vat_rate": "vat_percent",
            "total_amount_without_vat": "total_amount_without_vat",
            "total_vat_amount": "total_vat_amount",
            "total_amount_with_vat": "total_amount_with_vat",
            "discount_amount": "discount_amount",
            "total_amount_with_vat_in_words": "total_amount_with_vat_in_words",
        }
        for k, v in map_.items():
            if k in data:
                self[v] = data[k] or False

        try:
            vat_rate = float(data["vat_rate"].replace("%", ""))
        except:
            vat_rate = 0
        finally:
            self.vat_percent = vat_rate

        try:
            self.currency_id = self.env["res.currency"].search(
                [("name", "=", data["currency"])]
            )
        except:
            pass
        # TODO: payment method and status
        self.payment_status = (
            PAYMENT_STATUS_NOT_PAID_YET
            if data["payment_status"] == "unpaid"
            else PAYMENT_STATUS_PAID
        )

    def __update_seller_info(self, data: dict):
        map_ = {
            "seller_name": "seller_name",
            "seller_tax_code": "seller_tax_code",
            "seller_address": "seller_address",
            "seller_phone_number": "seller_phone_number",
            "seller_email": "seller_email",
            "seller_code": "seller_code",
            "seller_bank_name": "seller_bank_name",
            "seller_bank_account": "seller_bank_account",
            "seller_website": "seller_website",
        }
        for k, v in map_.items():
            if k in data:
                self[v] = data[k] or False

    def __update_buyer_info(self, data: dict):
        map_ = {
            "buyer_name": "buyer_name",
            "buyer_company_name": "buyer_company_name",
            "buyer_tax_code": "buyer_tax_code",
            "buyer_address": "buyer_address",
            "buyer_phone_number": "buyer_phone_number",
            "buyer_email": "buyer_email",
            "buyer_code": "buyer_code",
            "buyer_bank_name": "buyer_bank_name",
            "buyer_bank_account": "buyer_bank_account",
            "buyer_note": "buyer_note",
        }
        for k, v in map_.items():
            if k in data:
                self[v] = data[k] or False

    def __update_item_info(self, data: List[dict]):
        for no, item in enumerate(data, start=1):
            item_data = item.copy()
            # because some note does not have id number, so just follow created order
            item_data["line_number"] = no
            self.__update_item_info_detail(item_data)

    def __update_item_info_detail(self, data: dict):
        try:
            vat_rate = float(data["item_vat_rate"].replace("%", ""))
        except:
            vat_rate = 0
        try:
            price_subtotal = float(data["item_price_subtotal"])
        except:
            price_subtotal = 0
        try:
            price_total = float(data["item_price_total"])
        except:
            price_total = 0
        try:
            vat_amount = float(data["item_vat_amount"])
        except:
            vat_amount = 0

        # TODO: this should processed in another place, but I have no idea which place now
        # correction data for sinvoice v1
        if self.einvoice_template_id.provider == "sinvoice_v1":
            if data["type"] == INVOICE_LINE_TYPE_PRODUCT:
                # correct price_total base on subtotal and vat
                price_unit = float(data["item_price_unit"])
                if vat_rate and (price_subtotal == price_total):
                    # vat is available but subtotal = total => need to re-calc total
                    price_total = (
                        price_unit * float(data["item_quantity"]) * (1 + vat_rate / 100)
                    )
                # re correct vat_amount
                if vat_amount == 0 and (price_total != price_subtotal):
                    vat_amount = price_total - price_subtotal

        existed = self.env["ntp.einvoice.line"].search(
            [
                ("einvoice_id", "=", self.id),
                ("name", "=", data["item_name"]),
                ("line_number", "=", data["line_number"]),
            ]
        )
        if existed:
            existed.ensure_one()
            existed.update(
                {
                    "line_type": data["type"],
                    "quantity": data["item_quantity"],
                    "vat_percent": vat_rate,
                    "price_subtotal": price_subtotal,
                    "price_total": price_total,
                    "vat_amount": vat_amount,
                }
            )
            return
        map_ = {
            "type": "line_type",
            "line_number": "line_number",
            "item_code": "product_code",
            "item_name": "name",
            "item_uom": "product_uom",
            "item_price_unit": "price_unit_without_tax",
            "item_quantity": "quantity",
            # "item_vat_rate": "",
            # "item_price_subtotal": "price_subtotal",
            # "item_price_total": "price_total",
            # "item_vat_amount": "vat_amount",
            "x_provider_data": json.dumps(data),
        }
        data_to_create = {
            "product_id": False,
            "einvoice_id": self.id,
            "vat_percent": vat_rate,
            "price_subtotal": price_subtotal,
            "price_total": price_total,
            "vat_amount": vat_amount,
        }
        for k, v in map_.items():
            if k in data:
                data_to_create[v] = data[k] or False
        self.env["ntp.einvoice.line"].create(data_to_create)

    def __update_x_provider_display_data(self, data: List[List]):
        self.x_provider_display_data = build_table_result(data)

    def button_fillup_product_id(self):
        for line in self.einvoice_line_ids:
            line.button_fillup_product_id()

    def button_sync_smart(self):
        temp_wizard = self.env["ntp.einvoice.sync.from.provider"].create(vals_list={})
        for rec in self:
            if rec.name and rec.name != "/" and rec.provider_einvoice_status != "draft":
                temp_wizard.einvoice_id = rec
                temp_wizard.update_attachment_data = "xml"
                temp_wizard.update_detail_from_xml = True
                temp_wizard.update_provider_einvoice_status = True
                temp_wizard.update_payment_status = True
                temp_wizard.button_perform_update()
                rec._compute_x_is_product_id_filled()
                if not rec.x_is_product_id_filled:
                    rec.button_fillup_product_id()

    def button_send_email(self):
        self.ensure_one()
        context = {"default_einvoice_id": self.id}
        if self.invoice_address:
            context.update({"default_invoice_address": self.invoice_address.id})
        else:
            context.update({"default_invoice_address": self.partner_id.id})
        if self.buyer_email and self.buyer_address not in [
            self.invoice_address.email,
            self.partner_id.email,
        ]:
            context.update({"default_cc_email_address": self.buyer_email})
        return {
            "type": "ir.actions.act_window",
            "name": "Send Email To Customer",
            "res_model": "ntp.einvoice.send.email",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def task_sync_einvoice_info(self):
        per_each_run = 50
        invoices = self.env["ntp.einvoice"].search(
            [
                ("provider_einvoice_status", "not in", ["draft"]),
                ("einvoice_line_ids", "=", False),
            ]
        )
        cnt = 0
        for invoice in invoices:
            try:
                if cnt > per_each_run:
                    logger.info(
                        f"task_sync_einvoice_info > cross limit {per_each_run}, wait for next run"
                    )
                    break
                logger.info(
                    f"perform >> button_sync_smart from cron for {invoice.name}"
                )
                invoice.button_sync_smart()
                self.env.cr.commit()
                cnt += 1
            except Exception as e:
                logger.error(
                    f"perform FAILED >> button_sync_smart from cron for {invoice.name}",
                    exc_info=True,
                )
