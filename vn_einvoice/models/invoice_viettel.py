# -*- coding: utf-8 -*-
import re
import time
import base64
import logging
import requests
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
from requests.auth import HTTPBasicAuth
from num2words import num2words

from bs4 import BeautifulSoup
from odoo import models, fields, api, _
from odoo.exceptions import UserError

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
except AttributeError:
    # no pyopenssl support used / needed / available
    pass

_logger = logging.getLogger(__name__)

from ..api.sinvoice import SInvoiceApi


class InvoiceViettel(models.Model):
    _name = "invoice.viettel"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_invoice desc'

    name = fields.Char("Số Hóa Đơn", default="New")
    vsi_status = fields.Selection([
        ('draft', 'Đã Tạo Dự Thảo'),
        ('creating', 'Đang Phát Hành'),
        ('created', 'Đã Phát Hành'),
        ('canceled', 'Đã Hủy'),
    ], string=u'Trạng thái HĐĐT', default='draft', copy=False, tracking=True)
    date_invoice = fields.Date("Ngày hoá đơn")
    payment_term_id = fields.Many2one('account.payment.term')
    partner_id = fields.Many2one("res.partner", string="Tên doanh nghiệp")
    reference = fields.Char()
    company_id = fields.Many2one('res.company', string="Công ty",
                                 default=lambda self: self.env.user.company_id)
    company_branch_id = fields.Many2one('company.branch', string=_("Company Branch"))
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    journal_id = fields.Many2one('account.journal')
    invoice_line_ids = fields.One2many(
        'invoice.viettel.line', 'invoice_id', string="Sản phẩm")
    amount_tax = fields.Integer("Tiền thuế")
    amount_total = fields.Integer("Tiền sau thuế")
    residual = fields.Integer("Tổng tiền")
    access_token = fields.Char("Token")
    user_id = fields.Many2one('res.users')
    buyerName = fields.Char('Người mua hàng')

    account_move_ids = fields.Many2many(
        "account.move", string="Hoá đơn nội bộ")

    tax_company = fields.Char(
        "Mã số thuế", related="company_branch_id.vsi_tin")
    street_company = fields.Char(
        "Địa chỉ công ty", related="company_id.street")
    VAT = fields.Char("VAT", related="partner_id.vat")
    street_partner = fields.Char("Địa chỉ", related="partner_id.street")
    email_partner = fields.Char("Email", related="partner_id.email")
    phone_partner = fields.Char("Điện thoại", related="partner_id.phone")
    vsi_tin = fields.Char("Mã số thuế", related="company_branch_id.vsi_tin")
    vsi_template_type = fields.Char("Mã loại hóa đơn", related="company_branch_id.vsi_template_type")
    vsi_template = fields.Char(
        "Mẫu Hóa Đơn", related="company_branch_id.vsi_template")
    vsi_series = fields.Char(
        "Ký hiệu hóa đơn", related="company_branch_id.vsi_series")
    additionalReferenceDesc = fields.Char("Văn bản thoả thuận")
    additionalReferenceDate = fields.Datetime("Ngày thỏa thuận")
    invoiceStatus = fields.Selection([
            ('0', _(u'Không lấy hóa đơn')),
            ('1', _(u'Lấy hóa đơn ngay')),
            ('2', _(u'Lấy hóa đơn sau'))
        ],
        string="Invoice Status")
    origin_invoice = fields.Many2one(
        "invoice.viettel", "Hóa đơn cần điều chỉnh")
    is_adjustment_invoice = fields.Boolean(string="Hóa đơn điều chỉnh")
    adjustment_type = fields.Selection(
        [('1', _('Hóa đơn điều chỉnh tiền')),
         ('2', _('Hóa đơn điều chỉnh thông tin'))],
        string="Loại điều chỉnh")
    adjustment_desc = fields.Char("Adjustment Reference", help="Thông tin tham khào nếu có kèm theo của hóa đơn: văn bản thỏa thuận giữa bên mua và bên bán về việc thay thế, điều chỉnh hóa đơn.")
    adjustment_date = fields.Date("Adjustment Date", help="Thời gian phát sinh văn bản thỏa thuận giữa bên mua và bên bán")
    fkey = fields.Char("Mã Kỹ Thuật")
    pdf_file = fields.Many2one("ir.attachment", "File Hóa Đơn PDF")
    zip_file = fields.Many2one("ir.attachment", "Zip File")

    # Các trường này trên Invoice Viettel
    invoiceId = fields.Char("Viettel InvoiceID")
    invoiceType = fields.Char('invoiceType')
    originalInvoice = fields.Char('Original S-Invoice')
    adjustmentType = fields.Selection([
            ('1', _(u'Original Invoice')),
            ('3', _(u'Replacement Invoice')),
            ('7', _(u'Cancelled Invoice'))
        ], string=_("Invoice Type"))
    taxRate = fields.Char('Thuế suất GTGT', default="10",
                          help='Thuế suất, gõ 10 nếu 10%, 5 nếu 5%, 0 nếu 0%, gõ / nếu không có thuế')
    templateCode = fields.Char('templateCode')
    invoiceSeri = fields.Char('invoiceSeri')
    invoiceNumber = fields.Char('invoiceNumber')
    invoiceNo = fields.Char('invoiceNo')
    currency = fields.Char('currency')
    supplierTaxCode = fields.Char('supplierTaxCode')
    buyerTaxCode = fields.Char('buyerTaxCode')
    buyerIdNo = fields.Char('buyerIdNo')

    total = fields.Char('total')
    issueDate = fields.Char('issueDate')
    issueDateStr = fields.Char('issueDateStr')
    requestDate = fields.Char('requestDate')
    description = fields.Char('description')
    buyerCode = fields.Char('buyerCode')
    paymentStatus = fields.Char('paymentStatus')
    viewStatus = fields.Char('viewStatus')
    exchangeStatus = fields.Char('exchangeStatus')
    numOfExchange = fields.Char('numOfExchange')
    createTime = fields.Char('createTime')
    contractId = fields.Char('contractId')
    contractNo = fields.Char('contractNo')
    totalBeforeTax = fields.Char('totalBeforeTax')

    paymentMethod = fields.Char('paymentMethod')
    taxAmount = fields.Char('taxAmount')
    paymentTime = fields.Char('paymentTime')

    paymentStatusName = fields.Char('paymentStatusName')
    grossvalue = fields.Float(string="Tổng tiền trước thuế")
    grossvalue0 = fields.Float(string="Tổng tiền không thuế 0")
    grossvalue5 = fields.Float(string="Tổng tiền không thuế 5")
    grossvalue10 = fields.Float(string="Tổng tiền không thuế 10")
    vatamount5 = fields.Float(string="Tổng tiền thuế 5")
    amount_untaxed = fields.Integer("Tiền trước thuế")
    vatamount10 = fields.Float(string="Tổng tiền thuế 10")
    amountinwords = fields.Char(string="Tiền bằng chữ",
                                compute="_sub_amount_total")
    svcustomerName = fields.Char('Tên xuất hóa đơn',
                                 index=True, store=True, compute="_sv_name")
    paymentType = fields.Selection(
        [('ck', 'CK'),
         ('tm', 'TM'),
         ('hàng tặng không thu tiền', 'Hàng tặng không thu tiền'),
         ('hàng bảo hành không thu tiền', 'Hàng bảo hành không thu tiền'),
         ('tm/ck', 'TM/CK')],
        string="Hình thức thanh toán", default='tm/ck')
    reservation_code = fields.Char(string="Mã số bí mật")
    transaction_id = fields.Char(string="Transaction ID")
    errorCode = fields.Char(string="Invoice Approve Status")
    errorDescription = fields.Char(string="Invoice Approve Note")

    # internal odoo state
    state = fields.Selection([
            ('draft', 'Draft'),
            ('to_validate', 'To Validate'),
            ('validated', 'Validated'),
        ],
        "State",
        store=False,
        compute="_compute_state",
        default="draft")
    is_validated = fields.Boolean()

    x_is_match_amount_invoice = fields.Boolean(store=False, compute="_compute_match_amount")
    x_account_move_amount_untaxed = fields.Monetary(store=False, compute="_compute_match_amount")
    x_account_move_amount_total = fields.Monetary(store=False, compute="_compute_match_amount")

    def _compute_state(self):
        for rec in self:
            rec.state = 'draft'
            if rec.is_validated:
                rec.state = 'validated'
            elif rec.account_move_ids:
                rec.state = 'to_validate'

    def _compute_match_amount(self):
        for rec in self:
            rec.x_is_match_amount_invoice = False
            rec.x_account_move_amount_untaxed = 0
            rec.x_account_move_amount_total = 0

            if rec.account_move_ids:
                for invoice in rec.account_move_ids:
                    rec.x_account_move_amount_untaxed += invoice.amount_untaxed_signed
                    rec.x_account_move_amount_total += invoice.amount_total_signed

            if rec.x_account_move_amount_untaxed == rec.amount_untaxed \
                and rec.x_account_move_amount_total == rec.amount_total:
                rec.x_is_match_amount_invoice = True

    @api.onchange('invoice_line_ids')
    def _sub_total(self):
        for rec in self:
            tax5 = 0
            tax10 = 0
            gross5 = 0
            gross10 = 0
            amount_untaxed = 0
            amount_tax = 0
            for line in rec.invoice_line_ids:
                amount_untaxed += line.price_subtotal
                # if line.vat_rate == 5:
                #     tax5 += line.vat_amount
                #     gross5 += line.price_total
                # if line.vat_rate == 10:
                #     tax10 += line.vat_amount
                #     gross10 += line.price_total
                # must use this method to get exact vat,
                # and after that rounding it at the end
                amount_tax += line.get_vat_amount_exact()

            rec.amount_untaxed = amount_untaxed
            rec.amount_tax = rec.currency_id.round(amount_tax)
            rec.amount_total = rec.amount_tax + rec.amount_untaxed
            rec.grossvalue5 = gross5
            rec.grossvalue10 = gross10
            rec.vatamount5 = tax5
            rec.vatamount10 = tax10

    @api.depends('amount_total')
    def _sub_amount_total(self):
        for rec in self:
            rec.amount_total = rec.amount_tax + rec.amount_untaxed
            try:
                rec.amountinwords = num2words(
                    int(rec.amount_total), lang='vi_VN').capitalize() + " đồng chẵn."
            except NotImplementedError:
                rec.amountinwords = num2words(
                    int(rec.amount_total), lang='en').capitalize() + " VND."

    def download_file_pdf(self):
        self.check_config_einvoice()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        api_url = self.company_branch_id.vsi_domain + '/createExchangeInvoiceFile'
        data = {
            "supplierTaxCode": self.vsi_tin,
            "invoiceNo": self.name,
            "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S"),
            "exchangeUser": self.env.user.name
        }
        _logger.info("Einvoice Download Request Data: %s", data)
        result = requests.post(
            api_url, auth=HTTPBasicAuth(self.company_branch_id.vsi_username, self.company_branch_id.vsi_password), data=data, headers=headers)
        # _logger.info("Einvoice Download Result: %s", result.text)
        if not result.json()["errorCode"]:
            ir_attachment_id = self.env['ir.attachment'].create({
                'name': result.json()["fileName"] + '.pdf',
                'type': 'binary',
                'datas': result.json()["fileToBytes"],
                'store_fname': result.json()["fileName"] + '.pdf',
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/x-pdf'
            })
            self.pdf_file = ir_attachment_id
        else:
            raise UserError("Download Invoice PDF Result: %s" % result.text)

    # Huy hoa don
    def cancel_invoice_comfirm_OLD(self):
        self.check_config_einvoice()
        self.insert_log("Click Huỷ hoá đơn")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "supplierTaxCode": self.vsi_tin,
            "templateCode": self.vsi_template,
            "invoiceNo": self.name,
            "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S"),
            "additionalReferenceDesc": "hello",
            "additionalReferenceDate": fields.Datetime.now().strftime("%Y%m%d%H%M%S")
        }
        api_url = self.company_branch_id.vsi_domain + '/cancelTransactionInvoice'
        result = requests.post(
            api_url, auth=HTTPBasicAuth(self.company_branch_id.vsi_username, self.company_branch_id.vsi_password), data=data, headers=headers)
        if not result.json()["errorCode"]:
            self.vsi_status = 'canceled'
            if len(self.account_move_ids) > 0:
                for account_move_id in self.account_move_ids:
                    account_move_id.vsi_status = 'canceled'
        else:
            raise UserError(
                "Lỗi khi hủy hóa đơn " + result.text)

    def cancel_invoice_comfirm(self):
        self.check_config_einvoice()
        self.insert_log("Click Huỷ hoá đơn")
        sinvoice_api = SInvoiceApi(self.company_branch_id)
        result = sinvoice_api.act_cancel_invoice(
            self.invoiceNo or self.name,
            "cancel this invoice from odoo",
            fields.Datetime.now()
        )
        if result.status_code == 200:
            self.vsi_status = 'canceled'
            if len(self.account_move_ids) > 0:
                for account_move_id in self.account_move_ids:
                    account_move_id.vsi_status = 'canceled'

    def confirmPayment(self):
        self.check_config_einvoice()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.paymentType is not False:
            data = {
                "supplierTaxCode": self.vsi_tin,
                "templateCode": self.vsi_template,
                "invoiceNo": self.name,
                "buyerEmailAddress": self.email_partner,
                "paymentType": dict(self._fields['paymentType'].selection).get(self.paymentType),
                "paymentTypeName": dict(self._fields['paymentType'].selection).get(self.paymentType),
                "custGetInvoiceRight": True,
                "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S")
            }
        else:
            raise UserError("Choose payment type first")
        api_url = self.company_branch_id.vsi_domain + '/updatePaymentStatus'
        result = requests.post(api_url, auth=HTTPBasicAuth(self.company_branch_id.vsi_username, self.company_branch_id.vsi_password), params=data, headers=headers)
        _logger.info("Confirm Payment Result: %s", result.text)

    def unconfirmPayment(self):
        self.check_config_einvoice()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "supplierTaxCode": self.vsi_tin,
            "invoiceNo": self.name,
            "strIssueDate": self.date_invoice.strftime("%Y%m%d%H%M%S")
        }
        api_url = self.company_branch_id.vsi_domain + '/cancelPaymentStatus'
        result = requests.post(api_url, auth=HTTPBasicAuth(self.company_branch_id.vsi_username, self.company_branch_id.vsi_password), params=data, headers=headers)
        _logger.debug("Cancel Payment Result: %s", result.text)

    def reset_einvoice_status(self):
        self.insert_log("Click Reset trạng thái")
        self.write({
            'vsi_status': 'draft'
        })

    def set_validated(self):
        self.is_validated = True

    def button_confirm(self):
        self.ensure_one()
        if self.x_is_match_amount_invoice:
            self.set_validated()
        else:
            return {
                "type": "ir.actions.act_window",
                "name": "Confirm S-Invoice Valid",
                "res_model": "invoice.viettel.validate.confirm",
                "view_type": "form",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_currency_id": self.currency_id.id,
                    "default_sinvoice_id": self.id,
                    "default_invoice_total_amount_without_vat": self.x_account_move_amount_untaxed,
                    "default_invoice_total_amount_with_vat": self.x_account_move_amount_total,
                    "default_difference_amount_without_vat": self.amount_untaxed - self.x_account_move_amount_untaxed,
                    "default_difference_amount_with_vat": self.amount_total - self.x_account_move_amount_total,
                },
            }

    def button_to_validate(self):
        self.is_validated = False

    def resend_vnpt_email(self):
        self.insert_log("Click Download và Gửi Lại Hóa Đơn")
        # check xem da download pdf chua
        if len(self.pdf_file) == 0:
            self.download_file_pdf()

    def send_email_create_invoice(self):
        partner_id_array = []
        partner_ids = []
        if len(self.account_move_ids) > 0:
            for account_move_id in self.account_move_ids:
                partner_ids.append(
                    (4, account_move_id.invoice_user_id.partner_id.id))
                partner_id_array.append(account_move_id.invoice_user_id.partner_id.id)
                account_move_id.invoice_user_id.partner_id.id

        partner_name = self.partner_id.name
        if self.partner_id.company_type == 'employer' \
                and self.partner_id.customerName is not False:
            partner_name = self.partner_id.customerName

        body_html = "Kính gửi Quý khách hàng, <br/>" + self.company_id.name + \
            " xin trân trọng cảm ơn Quý khách hàng đã sử dụng dịch vụ "
        body_html += "của chúng tôi. <br/><br/>"
        body_html += self.company_id.name + \
            " vừa phát hành hóa đơn điện tử đến Quý khách. <br/><br/>"
        body_html += """Hóa đơn của Quý khách hàng có thông tin như sau: <br/><br/>
                • Họ tên người mua hàng: """

        body_html += partner_name + "<br/> "

        if self.VAT is not False:
            body_html += "• Mã Số Thuế: " + self.VAT + "<br/>"

        body_html += "• Hóa đơn số: "
        body_html += self.name + " thuộc mẫu số " + \
            self.vsi_template + " và serial " + self.vsi_series

        body_html += "<br/><br/>Mọi thắc mắc xin vui lòng liên hệ " + \
            self.company_id.name
        body_html += "<br/>ĐC: " + self.company_id.street
        body_html += """<br/>
                Điện thoại : """
        body_html += self.company_id.phone
        body_html += """<br/>
                Trân trọng.<br/>
        """
        create_values = {
            'body_html': body_html,
            'email_from': self.company_id.email,
            'subject': _("Phát hành hóa đơn điện tử %s ") % self.name,
            'recipient_ids': partner_ids,
            'attachment_ids': [(6, 0, [self.pdf_file.id])]
        }
        self.with_context({'force_write': True}).message_request(
            body=create_values['body_html'],
            subject=create_values['subject'],
            message_type='email',
            subtype_xmlid=None,
            partner_ids=partner_id_array,
            attachment_ids=[self.pdf_file.id],
            add_sign=True,
            model_description=False,
            mail_auto_delete=False
        )

    def insert_log(self, message):
        self.message_post(
            body=message,
            message_type='comment',
            author_id=self.env.user.partner_id.id if self.env.user.partner_id else None,
            subtype_xmlid='mail.mt_comment',
        )

    def get_seller_code(self):
        sellerCode = '11111111'
        for account_move_id in self.account_move_ids:
            seller = account_move_id.invoice_user_id
            sellerCode = seller.update_to_einvoice(self.company_branch_id)
            break
        return sellerCode

    def sendeinvoice_OLD(self):
        self.insert_log("Click Phát Hành Hóa Đơn")
        self.with_context(force_write=True)
        # Check already created einvoice
        if self.vsi_status == 'created':
            raise UserError("Hóa đơn đã được tạo hóa đơn điện tử")
        elif self.vsi_status == 'creating':
            raise UserError("Hóa đơn đang được tạo hóa đơn điện tử")
        self.vsi_status = "creating"
        self._cr.commit()
        # Check config
        self.check_config_einvoice()

        generalInvoiceInfo = {
            "invoiceType": self.company_branch_id.vsi_template_type,
            "templateCode": self.company_branch_id.vsi_template,
            "invoiceSeries": self.company_branch_id.vsi_series or "",
            "currencyCode": self.currency_id.name,
            "adjustmentType": 1,
            "paymentStatus": False
        }

        #  Trong trường hợp sellerTaxCode không được truyền sang
        #  thì toàn bộ dữ liệu người bán hàng sẽ được lấy từ
        #  dữ liệu khai báo hệ thống hóa đơn điện tử
        #  được gán theo user đang xử dụng xác thực.
        payments = [
            {
                "paymentMethodName": dict(self._fields['paymentType'].selection).get(self.paymentType)
            }
        ]
        summarizeInfo = self.get_summarize_info()

        data = {
            "generalInvoiceInfo": generalInvoiceInfo,
            "buyerInfo": self.get_buyer_info(),
            "sellerInfo": {},
            "payments": payments,
            "itemInfo": self.get_item_info(),
            "summarizeInfo": summarizeInfo,
            "taxBreakdowns": self.get_tax_breakdown()
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_url = self.company_branch_id.vsi_domain + '/createInvoice/' + self.company_branch_id.vsi_tin
        if self.vsi_status == 'created':
            raise UserError("Hóa đơn đã được tạo hóa đơn điện tử")
        _logger.info("Einvoice Content : %s", data)
        self.insert_log("Bắt đầu kết nối S-Invoice và thực hiện phát hành HĐĐT")
        result = requests.post(
            api_url, auth=(self.company_branch_id.vsi_username, self.company_branch_id.vsi_password), json=data, headers=headers)
        _logger.info("Einvoice Result : %s", result.text)
        _logger.info("Request header - %s", result.request.headers)
        self.insert_log("Kết thúc kết nối S-Invoice. Kết quả: " + result.text)
        if not result.json()["errorCode"]:
            self.vsi_status = "created"
            self.name = result.json()["result"]["invoiceNo"]
            self.reservation_code = result.json()["result"]["reservationCode"]
            self.transaction_id = result.json()["result"]["transactionID"]
            try:
                time.sleep(2)
                # self.confirmPayment()
                time.sleep(2)
                self.download_file_pdf()
                time.sleep(2)
            except:
                pass

            if len(self.account_move_ids) > 0:
                for account_move_id in self.account_move_ids:
                    account_move_id.vsi_template = self.vsi_template
                    account_move_id.vsi_series = self.vsi_series
                    account_move_id.vsi_number = result.json()["result"]["invoiceNo"]
                    account_move_id.einvoice_date = self.date_invoice
                    account_move_id.vsi_status = 'created'

                self.insert_log(" Cập nhật số hóa đơn thành công ")
            self.vsi_status = "created"
        else:
            raise UserError(
                "Lỗi khi phát hành hóa đơn " + result.text)

    def sendeinvoice(self):
        self.insert_log("Click Phát Hành Hóa Đơn")
        self.with_context(force_write=True)
        # Check already created einvoice
        if self.vsi_status == 'created':
            raise UserError("Hóa đơn đã được tạo hóa đơn điện tử")
        elif self.vsi_status == 'creating':
            raise UserError("Hóa đơn đang được tạo hóa đơn điện tử")
        self.vsi_status = "creating"
        self._cr.commit()

        # prepare data
        generalInvoiceInfo = {
            "invoiceType": self.company_branch_id.vsi_template_type,
            "templateCode": self.company_branch_id.vsi_template,
            "invoiceSeries": self.company_branch_id.vsi_series or "",
            "currencyCode": self.currency_id.name,
            "adjustmentType": 1,
            "paymentStatus": False
        }

        #  Trong trường hợp sellerTaxCode không được truyền sang
        #  thì toàn bộ dữ liệu người bán hàng sẽ được lấy từ
        #  dữ liệu khai báo hệ thống hóa đơn điện tử
        #  được gán theo user đang xử dụng xác thực.
        payments = [
            {
                "paymentMethodName": dict(self._fields['paymentType'].selection).get(self.paymentType)
            }
        ]
        summarizeInfo = self.get_summarize_info()

        data = {
            "generalInvoiceInfo": generalInvoiceInfo,
            "buyerInfo": self.get_buyer_info(),
            "sellerInfo": {},
            "payments": payments,
            "itemInfo": self.get_item_info(),
            "summarizeInfo": summarizeInfo,
            "taxBreakdowns": self.get_tax_breakdown()
        }
        sinvoice_api = SInvoiceApi(self.company_branch_id)
        _logger.info("Einvoice Content : %s", data)
        self.insert_log("Bắt đầu kết nối S-Invoice và thực hiện phát hành HĐĐT")
        result = sinvoice_api.act_create_einvoice(data)
        _logger.info("Einvoice Result : %s", result.text)
        _logger.info("Request header - %s", result.request.headers)
        self.insert_log("Kết thúc kết nối S-Invoice. Kết quả: " + result.text)
        if not result.json()["errorCode"]:
            self.vsi_status = "created"
            self.name = result.json()["result"]["invoiceNo"]
            self.reservation_code = result.json()["result"]["reservationCode"]
            self.transaction_id = result.json()["result"]["transactionID"]
            # try:
            #     time.sleep(2)
            #     # self.confirmPayment()
            #     time.sleep(2)
            #     self.download_file_pdf()
            #     time.sleep(2)
            # except:
            #     pass

            if len(self.account_move_ids) > 0:
                for account_move_id in self.account_move_ids:
                    account_move_id.vsi_template = self.vsi_template
                    account_move_id.vsi_series = self.vsi_series
                    account_move_id.vsi_number = result.json()["result"]["invoiceNo"]
                    account_move_id.einvoice_date = self.date_invoice
                    account_move_id.vsi_status = 'created'

                self.insert_log(" Cập nhật số hóa đơn thành công ")
            self.vsi_status = "created"
        else:
            raise UserError(
                "Lỗi khi phát hành hóa đơn " + result.text)

    def adjust_einvoice(self):
        self.check_config_einvoice()
        self.insert_log("Click Phát Hành Hóa Đơn Điều Chỉnh")
        generalInvoiceInfo = {
            "invoiceType": self.vsi_template_type,
            "templateCode": self.vsi_template,
            "currencyCode": self.currency_id.name,
            "adjustmentType": 5,
            "adjustmentInvoiceType": self.adjustment_type,
            "originalInvoiceId": self.origin_invoice.name,
            "paymentStatus": False,
            "cusGetInvoiceRight": True,
            "transactionUuid": self.transaction_id or "",
            "originalInvoiceIssueDate": int(fields.Datetime.to_datetime(self.date_invoice).timestamp() * 1000),
            "additionalReferenceDesc": self.adjustment_desc or dict(self._fields['adjustment_type'].selection).get(self.adjustment_type) or "",
            "additionalReferenceDate": int(fields.Datetime.to_datetime(self.adjustment_date).timestamp() * 1000) if self.adjustment_date else int(fields.Datetime.now().timestamp() * 100)
        }
        payments = [{
            "paymentMethodName": dict(self._fields['paymentType'].selection).get(self.paymentType) or ""
        }]
        itemInfo = []
        line_no = 1
        for invoice_line in self.invoice_line_ids:
            itemInfo.append({
                "lineNumber": line_no,
                "itemName": invoice_line.name,
                "itemCode": invoice_line.product_id.default_code or "",
                "unitName": invoice_line.product_id.uom_id.name,
                "quantity": invoice_line.quantity,
                "unitPrice": invoice_line.price_unit,
                "itemTotalAmountWithoutTax": invoice_line.price_subtotal,
                'taxPercentage': invoice_line.vat_rate or 0,
                "taxAmount": invoice_line.vat_amount,
                "itemTotalAmountWithTax": invoice_line.price_total,
                "isIncreaseItem": invoice_line.is_increase_adj,
                "adjustmentTaxAmount": invoice_line.vat_amount
            })
            line_no += 1
        summarizeInfo = self.get_summarize_info()
        summarizeInfo['isTotalAmountPos'] = True
        summarizeInfo['isTotalTaxAmountPos'] = True
        summarizeInfo['isTotalAmtWithoutTaxPos'] = True
        summarizeInfo['isDiscountAmtPos'] = True
        headers = {"Content-Type": "application/json"}
        data = {
            "generalInvoiceInfo": generalInvoiceInfo,
            "buyerInfo": self.get_buyer_info(),
            "sellerInfo": {},
            "payment": payments,
            "itemInfo": itemInfo,
            "summarizeInfo": summarizeInfo,
            "taxBreakdowns": self.get_tax_breakdown()
        }
        _logger.info("Adjust Invoice Data: %s", data)
        api_url = self.company_branch_id.vsi_domain + '/createInvoice/' + self.vsi_tin
        result = requests.post(
            api_url, auth=HTTPBasicAuth(self.company_branch_id.vsi_username, self.company_branch_id.vsi_password), json=data, headers=headers)
        _logger.info("Adjust Invoice Result: %s", result.text)
        if not result.json()["errorCode"]:
            self.name = result.json()["result"]["invoiceNo"]
            self.reservation_code = result.json()["result"]["reservationCode"]
            self.transaction_id = result.json()["result"]["transactionID"]
            self.vsi_status = "created"
            try:
                time.sleep(2)
                # self.confirmPayment()
                time.sleep(2)
                self.download_file_pdf()
                time.sleep(2)
            except:
                pass
        else:
            raise UserError(
                "Phát hành hóa đơn không thành công: %s" % result.text)

    def unlink(self):
        for record in self:
            if record.vsi_status == 'created' and not self.env.context.get('force_write', False):
                raise UserError(_('This invoice ' + record.name +
                                  '(' + str(record.id) + ')' + ' is created, can not delete'))
        return super(InvoiceViettel, self).unlink()

    # def write(self, vals):
    #     for record in self:
    #         if self.env.context.get('force_write', False) or record.adjustment_type or \
    #             record.is_adjustment_invoice or \
    #                 'vsi_status' in vals or 'adjustment_type' in vals or \
    #                 'amount_total' in vals or 'pdf_file' in vals or 'name' in vals:
    #             return super(InvoiceViettel, record).write(vals)
    #         elif record.vsi_status == 'created':
    #             raise UserError(_('This invoice ' + record.name + '(' + str(record.id) + ')' +
    #                               ' is created. You can not update'))
    #     return super(InvoiceViettel, self).write(vals)

    def task_check_created_einvoice_at_vnpt(self):
        # Check config
        einvoices = self.env['invoice.viettel'].sudo().search([('vsi_status', '=', 'creating')])

        for einvoice in einvoices:
            if len(einvoice.company_branch_id) == 0:
                logging.info("Chưa chọn Cấu hình phát hành hóa đơn Company Branch")

            xmlformdata = """<?xml version="1.0" encoding="utf-8"?>
        <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:xsd="http://www.w3.org/2001/XMLSchema"
         xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
            <soap12:Body>
                <listInvByCusFkey xmlns="http://tempuri.org/">"""
            xmlformdata += "<key>" + einvoice.fkey + \
                           "</key><fromDate></fromDate><toDate></toDate><userName>" + einvoice.company_branch_id.vsi_username
            xmlformdata += "</userName><userPass>" + einvoice.company_branch_id.vsi_password + """</userPass>
                                    </listInvByCusFkey>
                            </soap12:Body>
                        </soap12:Envelope>
                        """
            headers = {"Content-Type": "application/soap+xml; charset=utf-8"}

            api_url = einvoice.company_branch_id.portal_service_domain
            result = requests.post(
                api_url, data=xmlformdata, headers=headers)
            result_soup = BeautifulSoup(result.content.decode("utf-8"), 'xml')
            readable_content = result_soup.listInvByCusFkeyResult.text
            if 'ERR' not in readable_content and BeautifulSoup(readable_content, 'xml').Data.Item != None:
                result_content_soup = BeautifulSoup(readable_content, 'xml').Data.Item
                invoice_no = result_content_soup.invNum.text
                einvoice.vsi_status = 'created'
                einvoice.name = invoice_no
                if len(einvoice.account_move_ids) > 0:
                    for account_move_id in einvoice.account_move_ids:
                        account_move_id.vsi_template = einvoice.vsi_template
                        account_move_id.vsi_series = einvoice.vsi_series
                        account_move_id.vsi_number = invoice_no
                        account_move_id.einvoice_date = einvoice.date_invoice
                        account_move_id.vsi_status = 'created'
                self._cr.commit()
            else:
                logging.info(
                    "Lỗi khi kiểm tra hóa đơn " + str(einvoice.id) + " Error" + readable_content)

    def get_buyer_info(self):
        bank = self.partner_id.bank_ids.filtered(lambda b: b.einvoice_bank == True)
        cus_bank_no = bank.acc_number if bank else ''
        cus_bank_name = bank.bank_id.name if bank else ''
        buyerInfo = {
            "buyerName": self.partner_id.name,
            "buyerTaxCode": self.VAT or "",
            "buyerAddressLine": self.street_partner or "",
            "buyerEmail": self.email_partner or "",
            "buyerBankName": cus_bank_name,
            "buyerBankAccount": cus_bank_no
        }
        if self.phone_partner:
            buyerInfo["buyerPhoneNumber"] = re.sub(r"[^0-9]", "", self.phone_partner)
        return buyerInfo

    def get_item_info(self):
        itemInfo = []
        line_no = 1
        for invoice_line in self.invoice_line_ids:
            itemInfo.append({
                "lineNumber": line_no,
                "itemName": invoice_line.name,
                "itemCode": invoice_line.product_id.default_code or "",
                "unitName": invoice_line.product_id.uom_id.name,
                "quantity": invoice_line.quantity,
                "unitPrice": invoice_line.price_unit,
                "itemTotalAmountWithoutTax": invoice_line.price_subtotal,
                'taxPercentage': invoice_line.vat_rate or 0,
                "taxAmount": invoice_line.vat_amount,
                "itemTotalAmountWithTax": invoice_line.price_total,
            })
            line_no += 1
        return itemInfo

    def check_config_einvoice(self):
        if len(self.company_branch_id) == 0:
            raise UserError("Chưa chọn Cấu hình phát hành hóa đơn Company Branch")

    def get_summarize_info(self):
        return {
            "sumOfTotalLineAmountWithoutTax": self.amount_untaxed,
            "totalAmountWithoutTax": self.amount_untaxed,
            "totalTaxAmount": self.amount_tax,
            "totalAmountWithTax": self.amount_total,
            "totalAmountWithTaxInWords": self.amountinwords,
            "taxPercentage": self.taxRate,
            "discountAmount": 0.0
        }

    def get_tax_breakdown(self):
        return [{
            "taxPercentage": self.taxRate,
            "taxableAmount": self.amount_untaxed,
            "taxAmount": self.amount_tax
        }]

    def sync_invoice_detail(self, type='zip'):
        """

        :return: dict : line detail
        """
        sinvoice_apis = {}
        for rec in self:
            invoiceNo = rec.invoiceNo or rec.name
            if not invoiceNo or invoiceNo == "New":
                # cannot do anything with invoice not having invoiceId
                continue
            if rec.company_branch_id.id not in sinvoice_apis:
                sinvoice_apis[rec.company_branch_id.id] = SInvoiceApi(rec.company_branch_id)
            sinvoice_api: "SInvoiceApi" = sinvoice_apis[rec.company_branch_id.id]
            data = sinvoice_api.act_get_invoice_attachment(rec.vsi_tin, rec.vsi_template, invoiceNo, type=type)
            detail_status = sinvoice_api.act_get_invoice_status_detail(invoiceNo)
            if detail_status:
                if detail_status["adjustmentType"]:
                    rec.adjustmentType = detail_status["adjustmentType"]
                if detail_status['reasonDelete']:
                    pass
                if detail_status['reservationCode']:
                    rec.reservation_code = detail_status['reservationCode']
                if detail_status['additionalReferenceDesc']:
                    rec.additionalReferenceDesc = detail_status['additionalReferenceDesc']
                if detail_status['additionalReferenceDate']:
                    rec.additionalReferenceDate = datetime.strptime(detail_status['additionalReferenceDate'], '%Y-%m-%dT%H:%M:%SZ')
                if detail_status['errorCode']:
                    rec.errorCode = detail_status['errorCode']
                if detail_status['errorDescription']:
                    rec.errorDescription = detail_status['errorDescription']
            if not data:
                raise UserError("cannot get attachment data")
            rec._update_attachments(data, type=type)
            if type == 'zip':
                xml_data = None
                # dont recreate invoice line if already has 1 here
                zipf = ZipFile(BytesIO(base64.b64decode(data.get('fileToBytes'))), 'r')
                for zinfo in zipf.filelist:
                    # sinvoice v1
                    if zinfo.filename.endswith('xml'):
                        xml_data = zipf.read(zinfo)
                    elif zinfo.filename.endswith('zip'):
                        # sinvoice v2
                        zipf_zip = ZipFile(BytesIO(zipf.read(zinfo)), 'r')
                        xml_zinfo = [zinfo_sub for zinfo_sub in zipf_zip.filelist if zinfo_sub.filename.endswith("xml")]
                        if xml_zinfo:
                            xml_data = zipf_zip.read(xml_zinfo[0])
                if not xml_data:
                    return
                if rec.adjustmentType != '7':
                    rec.vsi_status = 'created'
                else:
                    rec.vsi_status = 'canceled'
                bs_content = BeautifulSoup(xml_data, 'xml')
                lines_detail = bs_content.find_all('HHDVu')
                rec.amount_untaxed = 0
                rec.amount_tax = 0
                rec.paymentType = bs_content.find('HTTToan').text.lower()
                if bs_content.find("TgTCThue").text:
                    rec.amount_untaxed = float(bs_content.find("TgTCThue").text)
                if bs_content.find("TgTThue").text:
                    rec.amount_tax = float(bs_content.find("TgTThue").text)
                # correct fix taxRate from invoice
                try:
                    rec.taxRate = float(bs_content.find("THTTLTSuat").findChildren("LTSuat")[0].findChildren("TSuat")[0].text.replace("%", ""))
                except Exception as e:
                    # decide tax
                    # FIXME: it need to be a more elegant way
                    if rec.amount_untaxed:
                        rec.taxRate = round(rec.amount_tax/rec.amount_untaxed*100)
                    # rec._sub_total()
                    # rec._sub_amount_total()
                for line in lines_detail:
                    rec.create_detail_mapping(line)

    def create_detail_mapping(self, detail):
        mapping_data = {
            'product_id': 'MHHDVu',
            'quantity': 'SLuong',
            'actual_price_unit': 'DGia',
            'price_unit': 'DGia',
            'price_total': 'ThTien',
            'price_subtotal': 'ThTien',
            'invoice_uom_id': 'DVTinh',
            'invoice_line_tax_ids': 'TSuat',
            'name': 'THHDVu'
        }
        detail_data = {'invoice_id': self.id}
        amount_untaxed = 0
        for value, key in mapping_data.items():
            data_get = detail.find(key).text
            if data_get == '':
                continue
            if value == 'product_id':
                product_id = self.env['product.product'].search([('default_code', 'ilike', data_get)])
                if not product_id:
                    product_id = self.env['product.product'].search([('default_code', 'ilike', data_get.split(']')[0][1:])])
                detail_data.update({value: product_id.id or False, 'uom_id': product_id.uom_id.id})
            elif value == 'invoice_line_tax_ids':
                tax_id = self.env['account.tax'].search([('type_tax_use', '=', 'sale'), ('amount', '=', int(data_get.replace('%', ''))),
                                                ('price_include', '=', False)])
                detail_data.update({value: tax_id.id or False,})
            else:
                detail_data.update({value: data_get})
                if key == 'ThTien':
                    amount_untaxed = float(data_get)
        # checking
        cnt = self.env['invoice.viettel.line'].search_count([
            ('invoice_id', '=', detail_data['invoice_id']),
            ('name', '=', detail_data['name'])]
        )
        if not cnt:
            self.env['invoice.viettel.line'].create(detail_data)

    @api.model
    def sync_s_invoice(self, *arg):
        for branch in self.env['company.branch'].search([]):
            if branch.vsi_auto_pull:
                if branch.vsi_version == 'v1':
                    self.pull_all_invoice_v1(branch)
                elif branch.vsi_version == 'v2':
                    self.pull_all_invoice_v2(branch)
                else:
                    raise ValueError("invalid config")
        res = {"type": "ir.actions.client", "tag": "reload"}
        return res

    def create_picking_move(self):
        for r in self:
            picking_id = self.env['stock.picking'].create(r._get_new_picking_values())
            for line in r.invoice_line_ids:
                if line.quantity == 0:
                    continue
                try:
                    self.env['stock.move'].create(line._prepare_move_line_vals(picking_id))
                except:
                    print(1)
        return

    def create_account_move_invoice(self):
        for r in self:
            invoice_data = r.prepare_invoice_data()
            self.env['account.move'].create(invoice_data)
        return

    def prepare_invoice_data(self):
        invoice_line = []
        for line in self.invoice_line_ids:
            data_line = {
                'product_id': line.product_id.id,
                'price_subtotal': (line.price_subtotal),
                'price_total':(line.price_total),
                'price_unit':(line.actual_price_unit),
                'quantity': line.quantity,
                'name': line.name,
                'tax_ids': [(6, 0, line.invoice_line_tax_ids.ids)],
                'product_uom_id': line.uom_id.id,
            }
            invoice_line.append([0, 0, data_line])
        return {'partner_id': self.partner_id.id,
                'invoice_date': self.date_invoice,
                'invoiceStatus': self.invoiceStatus,
                'company_branch_id': self.company_branch_id.id,
                'move_type': 'out_invoice',
                'vsi_status': 'created',
                'journal_id': self.env['account.journal'].search([('code', '=', 'INV')]).id or False,
                'invoice_viettel_ids': [(6, 0, self.ids)],
                'invoice_line_ids': invoice_line,
                }

    def pull_all_invoice_v1(self, company_branch_id):
        api_url = company_branch_id.vsi_domain + '/getInvoices/' + company_branch_id.vsi_tin
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+07:00'
        data = {
            "startDate": "2022-01-01T03:14:32.611+07:00",
            "endDate": now,
            "rowPerPage": 2000,
            # "pageNum": 1
        }

        _logger.info("Einvoice Content : %s", data)
        result = requests.post(
            api_url, auth=HTTPBasicAuth(company_branch_id.vsi_username, company_branch_id.vsi_password),
            json=data, headers=headers)

        if not result.json()["errorCode"]:
            for invoice in result.json().get('invoices'):
                existed_invoice = self.search([('name', '=', invoice.get("invoiceNo",  ""))])
                if existed_invoice:
                    continue
                else:
                    data_invoice = invoice.copy()
                    data_invoice.update(company_branch_id=company_branch_id.id,
                                        VAT=data_invoice.get("buyerTaxCode",  "") or data_invoice.get("buyerIdNo",  "") ,
                                        street_partner=data_invoice.get("buyerAddressLine",  ""),
                                        email_partner=data_invoice.get("buyerEmail",  ""),
                                        phone_partner=data_invoice.get("buyerPhoneNumber",  ""),
                                        name=data_invoice.get("invoiceNo",  ""),
                                        date_invoice=datetime.fromtimestamp(data_invoice.get('createTime')/1000),
                                        amount_untaxed=data_invoice.get("totalBeforeTax",  0),
                                        amount_tax=data_invoice.get("taxAmount",  0),
                                        partner_id=self._get_res_partner(data_invoice.get("buyerTaxCode",  "") or data_invoice.get("buyerIdNo",  "")),
                                        amount_total=data_invoice.get("total",  0),
                                        invoiceStatus=str(data_invoice.get("viewStatus",  0) or 0),
                                        currency_id=self.env['res.currency'].search([('name', '=', data_invoice.get("currency", ''))]).id or self.env.company.currency_id
                    )

                    for key, value in invoice.items():
                        if not value:
                            data_invoice.pop(key)
                    try:
                        _logger.info('start to create s-invoice %s'%(data_invoice.get('name')))
                        invoice_viettel = self.env['invoice.viettel'].create(data_invoice)
                        invoice_viettel.sync_invoice_detail('pdf')
                        _logger.info('Done to create s-invoice %s'%(data_invoice.get('name')))
                    except:
                        print('error when create S-invoice with data:' + str(data_invoice))

        else:
            raise UserError(
                "Lỗi khi lấy thông tin hóa đơn " + result.text)
        return

    def pull_all_invoice_v2(self, company_branch_id):
        sinvoice_api = SInvoiceApi(company_branch_id)
        invoices = sinvoice_api.act_get_invoices()
        for invoice in invoices:
            self._update_invoice(sinvoice_api, company_branch_id, invoice)

    def _update_attachments(self, data, type='pdf'):
        self.ensure_one()
        ir_attachment_id = self.env['ir.attachment'].search([
            ('name', '=', data["fileName"]),
            ('res_model', '=', self._name),
            ('res_id', '=', self.id)
            ], limit=1)
        if not ir_attachment_id:
            ir_attachment_id = self.env['ir.attachment'].create({
                'name': data["fileName"],
                'type': 'binary',
                'datas': data["fileToBytes"],
                'store_fname': data["fileName"],
                'res_model': self._name,
                'res_id': self.id
            })
            if type == 'pdf':
                self.pdf_file = ir_attachment_id
            elif type == 'zip':
                self.zip_file = ir_attachment_id
        return ir_attachment_id

    def _update_invoice(self, sinvoice_api: "SInvoiceApi", company_branch_id, invoice_dict):
        existed_invoice = self.search([('name', '=', invoice_dict.get("invoiceNo",  ""))])
        data_invoice = invoice_dict.copy()
        if existed_invoice:
            update_data = dict(
                amount_untaxed=data_invoice.get("totalBeforeTax",  0),
                amount_tax=data_invoice.get("taxAmount",  0),
                amount_total=data_invoice.get("total",  0),
                invoiceStatus=str(data_invoice.get("viewStatus",  0) or 0),
            )
            existed_invoice.update(update_data)

        else:
            data_invoice.update(
                company_branch_id=company_branch_id.id,
                VAT=data_invoice.get("buyerTaxCode",  "") or data_invoice.get("buyerIdNo",  "") ,
                street_partner=data_invoice.get("buyerAddressLine",  ""),
                email_partner=data_invoice.get("buyerEmail",  ""),
                phone_partner=data_invoice.get("buyerPhoneNumber",  ""),
                name=data_invoice.get("invoiceNo",  ""),
                # date_invoice=datetime.fromtimestamp(data_invoice.get('createTime')/1000),
                amount_untaxed=data_invoice.get("totalBeforeTax",  0),
                amount_tax=data_invoice.get("taxAmount",  0),
                partner_id=self._get_res_partner(data_invoice.get("buyerTaxCode",  "") or data_invoice.get("buyerIdNo",  "")),
                amount_total=data_invoice.get("total",  0),
                invoiceStatus=str(data_invoice.get("viewStatus",  0) or 0),
                currency_id=self.env['res.currency'].search([('name', '=', data_invoice.get("currency", ''))]).id or self.env.company.currency_id
            )

            if data_invoice.get('createTime'):
                data_invoice.update(date_invoice=datetime.fromtimestamp(data_invoice.get('createTime')/1000))
            else:
                data_invoice.update(date_invoice=datetime.strptime(data_invoice['issueDateStr'], '%Y-%m-%dT%H:%M:%SZ'))

            for key in list(data_invoice.keys()):
                # remove None/False/""
                if not data_invoice[key]:
                    data_invoice.pop(key)
                elif key in ['state', 'stateCode']:
                    data_invoice.pop(key)

            try:
                _logger.info('Start to create s-invoice %s'%(data_invoice.get('name')))
                invoice_viettel: "InvoiceViettel" = self.env['invoice.viettel'].create(data_invoice)
                ir_attachment_id = invoice_viettel._update_attachments(
                    data=sinvoice_api.act_get_invoice_attachment(
                        invoice_viettel.supplierTaxCode,
                        invoice_viettel.templateCode,
                        invoice_viettel.invoiceNo),
                    type='pdf'
                )
                _logger.info('Done to create s-invoice %s'%(data_invoice.get('name')))
            except Exception as e:
                raise

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
            ["&", ("vat", "=", vat), ("company_group", "=", True), ('parent_id', '=', False)],
        )
        if len(partner) == 1 and partner:
            return partner.id
        return False

    def _get_new_picking_values(self):
        """ return create values for new picking that will be linked with group
        of moves in self.
        """
        origin = self.name
        # Will display source document if any, when multiple different origins
        # are found display a maximum of 5
        # if len(origins) == 0:
        #     origin = False
        # else:
        #     origin = ','.join(origins[:5])
        #     if len(origins) > 5:
        #         origin += "..."
        partners = self.partner_id
        partner = len(partners) == 1 and partners.id or False
        warehouse = self.env['stock.warehouse'].search([('name', 'ilike', self.env.company.name)])
        picking_type = self.env['stock.picking.type'].search([('warehouse_id', '=', warehouse.id), ('sequence_code', '=', 'OUT')])
        return {
            'origin': origin,
            'company_id': self.env.company.id,
            'user_id': False,
            'move_type': 'direct',
            'partner_id': partner,
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': 9,
            'scheduled_date': datetime.strftime(self.account_move_ids.date, '%Y-%m-%d %H:%M:%S')
        }

    def create_stock_journal(self):
        for r in self:
            invoice_data = r.prepare_move_data()
            self.env['account.move'].create(invoice_data)
        return

    def prepare_move_data(self):
        line_ids = []
        journal_id = self.env['account.journal']
        for move in self.account_move_ids:
            for line in move.invoice_line_ids:
                if not line.product_id:
                    continue
                if not journal_id:
                    journal_id = line.product_id.categ_id.property_stock_journal
                debit_account_id = line.product_id.categ_id.property_stock_account_input_categ_id
                credit_account_id = line.product_id.categ_id.property_stock_valuation_account_id
                if not debit_account_id or not credit_account_id:
                    print ('error')
                cost_line = move.line_ids.filtered(lambda x: x.account_id == debit_account_id and x.product_id == line.product_id and x.quantity == line.quantity)
                cost = cost_line.credit
                line_ids += [(0, 0, line_vals) for line_vals in
                       self._generate_valuation_lines_data(line, self.partner_id.commercial_partner_id.id, line.quantity, cost, cost,
                                                           debit_account_id.id, credit_account_id.id, line.name).values()]

                # line_ids.append([0, 0, data_line])
        if not journal_id:
            return {}
        return {'partner_id': self.partner_id.id,
                'invoice_date': self.date_invoice,
                'date': self.date_invoice,
                'invoiceStatus': self.invoiceStatus,
                'company_branch_id': self.company_branch_id.id,
                'ref': self.name,
                'journal_id': journal_id.id or False,
                'line_ids': line_ids,
                'move_type': 'entry',
                }

    def _generate_valuation_lines_data(self, move_line, partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, description):
        # This method returns a dictionary to provide an easy extension hook to modify the valuation lines (see purchase for an example)
        self.ensure_one()
        debit_line_vals = {
            'name': description,
            'product_id': move_line.product_id.id,
            'quantity': qty,
            'product_uom_id': move_line.product_id.uom_id.id,
            'ref': description,
            'partner_id': partner_id,
            'debit': debit_value if debit_value > 0 else 0,
            'credit': -debit_value if debit_value < 0 else 0,
            'account_id': debit_account_id,
        }

        credit_line_vals = {
            'name': description,
            'product_id': move_line.product_id.id,
            'quantity': qty,
            'product_uom_id': move_line.product_id.uom_id.id,
            'ref': description,
            'partner_id': partner_id,
            'credit': credit_value if credit_value > 0 else 0,
            'debit': -credit_value if credit_value < 0 else 0,
            'account_id': credit_account_id,
        }

        rslt = {'credit_line_vals': credit_line_vals, 'debit_line_vals': debit_line_vals}
        if credit_value != debit_value:
            # for supplier returns of product in average costing method, in anglo saxon mode
            diff_amount = debit_value - credit_value
            price_diff_account = move_line.product_id.property_account_creditor_price_difference

            if not price_diff_account:
                price_diff_account = move_line.product_id.categ_id.property_account_creditor_price_difference_categ
            if not price_diff_account:
                raise UserError(_('Configuration error. Please configure the price difference account on the product or its category to process this operation.'))
        return rslt
