# -*- coding: utf-8 -*-
import time
import logging
import requests
import urllib3
import re
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

class InvoiceViettel(models.Model):
    _name = "invoice.viettel"
    _inherit = ['mail.thread', 'mail.activity.mixin']

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
    company_branch_id = fields.Many2one('company.branch', string="Company Branch")
    currency_id = fields.Many2one('res.currency')
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
    invoiceStatus = fields.Selection(
        [('0', _(u'Không lấy hóa đơn')), ('1', _(u'Lấy hóa đơn ngay')),
         ('2', _(u'Lấy hóa đơn sau'))], string="Invoice Status")
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

    # Các trường này trên Invoice Viettel
    invoiceId = fields.Char("Viettel InvoiceID")
    invoiceType = fields.Char('invoiceType')
    adjustmentType = fields.Char('adjustmentType')
    taxRate = fields.Char('Thuế suất GTGT', default="10",
                          help='Thuế suất, gõ 10 nếu 10%, 5 nếu 5%, 0 nếu 0%, gõ / nếu không có thuế')

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
         ('tm/ck', 'TM/CK')],
        string="Hình thức thanh toán", default='tm/ck')
    reservation_code = fields.Char(string="Mã số bí mật")
    transaction_id = fields.Char(string="Transaction ID")
    @api.onchange('invoice_line_ids')
    def _sub_total(self):
        for rec in self:
            tax = 0
            tax5 = 0
            tax10 = 0
            gross5 = 0
            gross10 = 0
            amount_untaxed = 0
            for line in rec.invoice_line_ids:
                amount_untaxed += line.price_total
                tax += line.vat_amount
                if line.vat_rate == 5:
                    tax5 += line.vat_amount
                    gross5 += line.price_total
                if line.vat_rate == 10:
                    tax10 += line.vat_amount
                    gross10 += line.price_total

            rec.amount_untaxed = amount_untaxed
            rec.amount_tax = rec.amount_total - rec.amount_untaxed
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
    def cancel_invoice_comfirm(self):
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
        self.with_context({'force_write': True}).message_post(
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
            raise UserError(
                "Hóa đơn đã được tạo hóa đơn điện tử")
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
            result_soup = BeautifulSoup(result.content.decode("utf- 8"), 'xml')
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
