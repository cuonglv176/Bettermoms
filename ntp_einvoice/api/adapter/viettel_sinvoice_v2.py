from datetime import date, datetime, timedelta
import json
import logging
from typing import List, Literal, Optional

from requests import Response

from .adapter_models import AdapterInvoiceBasicInfo

from ..viettel.sinvoice_v2 import SInvoiceApi
from ..viettel.sinvoice_v2_model import (
    Invoice_SearchInvoice,
    InvoiceTemplate as InvoiceTemplateModel,
)
from .base_adapter import *


logger = logging.getLogger(__name__)


class ViettelSInvoiceAdapter_v2(BaseAdapter):
    """
    Viettel SInvoice Adapter For V2

    Trạng thái điều chỉnh hóa đơn:
    1: Hóa đơn gốc
    3: Hóa đơn thay thế
    5: Hóa đơn điều chỉnh
    7: Hóa đơn xóa bỏ
    Không truyền sẽ mặc định là 1
    """

    @property
    def api(self):
        return SInvoiceApi(
            self.tax_code, self.api_username, self.api_password, self.api_domain
        )

    def build_data_for_provider(self, **conf):
        return super().build_data_for_provider(**conf)

    def __build_payments(self, data: EInvoice):
        payment_type_map = {
            PAYMENT_TYPE_CK: ["1", "CK"],
            PAYMENT_TYPE_TM: ["2", "TM"],
            PAYMENT_TYPE_TM_CK: ["3", "TM/CK"],
        }
        #
        payments = []
        if data.payment_type in [PAYMENT_TYPE_CK, PAYMENT_TYPE_TM, PAYMENT_TYPE_TM_CK]:
            payments.append(
                {
                    "paymentMethod": payment_type_map[data.payment_type][0],
                    "paymentMethodName": payment_type_map[data.payment_type][1],
                }
            )
        else:
            payments.append(
                {
                    "paymentMethod": "5",
                    "paymentMethodName": dict(
                        data._fields["payment_type"].selection
                    ).get(data.payment_type),
                }
            )
        return payments

    def __build_general_info(self, data: EInvoice):
        general_info = {
            "invoiceType": self.invoice_template_type,
            "templateCode": self.invoice_template,
            "invoiceSeries": self.invoice_series,
            "currencyCode": data.currency_id.name,
            "adjustmentType": 1,  # TODO: need to support it in odoo
            "paymentStatus": data.payment_status,
        }
        # unique id to avoid duplicating invoice
        # if data.transaction_uuid:
        #     general_info["transactionUuid"] = data.transaction_uuid
        if data.payment_status == PAYMENT_STATUS_NOT_PAID_YET:
            general_info.update({"paymentStatus": "0"})
        else:
            general_info.update({"paymentStatus": "1"})
        return general_info

    def __build_seller_info(self, data: EInvoice):
        seller_info = {
            "sellerLegalName": data.company_id.einvoice_legal_name,
            "sellerTaxCode": self.tax_code,
            "sellerAddressLine": data.company_id.einvoice_address,
            "sellerPhoneNumber": data.company_id.einvoice_phone_number,
            "sellerBankName": data.company_id.einvoice_bank,
            "sellerBankAccount": data.company_id.einvoice_bank_account,
            "sellerEmail": data.company_id.einvoice_email,
            "sellerWebsite": data.company_id.einvoice_website,
        }
        # pop out invalid value
        seller_info = {k: v for k, v in seller_info.items() if v not in [None, False]}
        return seller_info

    def __build_buyer_info(self, data: EInvoice):
        if data.buyer_type == BUYER_NOT_NEED_INVOICE:
            buyer_info = {
                "buyerNotGetInvoice": 1,
                "buyerName": "Người mua không lấy hóa đơn (Customer does not need invoice)",
                "buyerAddressLine": "./.",
            }
        else:
            buyer_info = {
                "buyerNotGetInvoice": 0,
                "buyerName": data.buyer_name,
                "buyerLegalName": data.buyer_company_name,
                "buyerTaxCode": data.buyer_tax_code,
                "buyerAddressLine": data.buyer_address,
                "buyerEmail": data.buyer_email,
                "buyerBankName": data.buyer_bank_name,
                "buyerBankAccount": data.buyer_bank_account,
                "buyerCode": data.buyer_code,
            }
        # pop out invalid value
        buyer_info = {k: v for k, v in buyer_info.items() if v not in [None, False]}
        return buyer_info

    def __build_item_info(self, data: EInvoice):
        item_info = []
        for no, item in enumerate(data.einvoice_line_ids, start=1):
            item: EInvoiceLine = item
            # only support item line = 2 => means note
            if item.line_type == "2":
                item_info_line = {
                    "selection": int(item.line_type),
                    "itemName": item.name,
                    # "itemCode": item.product_code or "",
                    # "unitName": item.product_uom,
                    # "unitCode": item.product_uom_id.name,
                    # "quantity": item.quantity,
                    # "unitPrice": item.price_unit_without_tax,
                    # "itemTotalAmountWithoutTax": item.price_subtotal,
                    # "taxPercentage": item.vat_percent or 0,
                    # "taxAmount": item.vat_amount,
                    # "itemTotalAmountWithTax": item.price_total,
                }
            else:
                item_info_line = {
                    "lineNumber": no,
                    "itemName": item.name,
                    "itemCode": item.product_code or "",
                    "unitName": item.product_uom,
                    "unitCode": item.product_uom_id.name,
                    "quantity": item.quantity,
                    "unitPrice": item.price_unit_without_tax,
                    "itemTotalAmountWithoutTax": item.price_subtotal,
                    "taxPercentage": item.vat_percent or 0,
                    "taxAmount": item.vat_amount,
                    "itemTotalAmountWithTax": item.price_total,
                }
            item_info.append(item_info_line)
        return item_info

    def __build_tax_breakdowns(self, data: EInvoice):
        tax_breakdowns = [
            {
                "taxPercentage": data.vat_percent,
                "taxableAmount": data.total_amount_without_vat,
                "taxAmount": data.total_vat_amount,
            }
        ]
        return tax_breakdowns

    def __build_summarize_info(self, data: EInvoice):
        summarize_info = {
            "sumOfTotalLineAmountWithoutTax": data.total_amount_without_vat,
            "totalAmountWithoutTax": data.total_amount_without_vat,
            "totalTaxAmount": data.total_vat_amount,
            "totalAmountWithTax": data.total_amount_with_vat,
            "totalAmountWithTaxInWords": data.total_amount_with_vat_in_words,
            "taxPercentage": data.vat_percent,
            "discountAmount": 0.0,
        }
        return summarize_info

    def __build_einvoice_data(self, data: EInvoice):
        general_info = self.__build_general_info(data)
        seller_info = self.__build_seller_info(data)
        buyer_info = self.__build_buyer_info(data)
        payments = self.__build_payments(data)
        item_info = self.__build_item_info(data)
        tax_breakdowns = self.__build_tax_breakdowns(data)
        summarize_info = self.__build_summarize_info(data)

        api_data = {
            "generalInvoiceInfo": general_info,
            "buyerInfo": buyer_info,
            "sellerInfo": seller_info,
            "payments": payments,
            "itemInfo": item_info,
            "summarizeInfo": summarize_info,
            "taxBreakdowns": tax_breakdowns,
        }
        logger.info(api_data)
        return api_data

    def get_preview_einvoice(self, data: EInvoice):
        api_data = self.__build_einvoice_data(data)
        api_model = InvoiceTemplateModel(**api_data)
        res, attachment = self.api.api_get_preview_invoice(api_model)
        if attachment:
            return res, {
                "file_name": attachment.fileName,
                "file_data": attachment.fileToBytes,
            }
        else:
            return res, {}

    def create_invoice(self, data: EInvoice):
        api_data = self.__build_einvoice_data(data)
        api_model = InvoiceTemplateModel(**api_data)
        res = self.api.api_do_invoice("create", api_model)
        return {
            "invoice_no": res.result.invoiceNo,
            "provider_data": res.result.dict(),
        }

    def get_invoice_attachment_pdf(self, data: EInvoice):
        pdf = self.api.api_get_invoice_attachment(
            template_code=data.einvoice_template_id.invoice_template,
            invoice_no=data.name,
            attachment_type="pdf",
        )

        return {
            "file_name": pdf.fileName,
            "file_data": pdf.fileToBytes,
        }

    def get_invoice_attachment_xml(self, data: EInvoice):
        xml = self.api.api_get_invoice_attachment(
            template_code=data.einvoice_template_id.invoice_template,
            invoice_no=data.name,
            attachment_type="zip",
        )
        return {
            "file_name": xml.fileName,
            "file_data": xml.fileToBytes,
        }

    def __parse_invoice_status(self, search: Invoice_SearchInvoice):
        map_ = {
            "1": PROVIDER_EINVOICE_STATUS_ISSUED,
            "3": PROVIDER_EINVOICE_STATUS_REPLACE,
            "5": PROVIDER_EINVOICE_STATUS_ADJUST,
            "7": PROVIDER_EINVOICE_STATUS_CANCELED,
            "9": PROVIDER_EINVOICE_STATUS_UNKNOWN,
        }
        status = map_[search.adjustmentType]
        return {"issue_date": search.issueDate.date(), "status": status}

    def __parse_invoice_payment_status(self, search: Invoice_SearchInvoice):
        map_ = {
            "1": PAYMENT_TYPE_CK,
            "2": PAYMENT_TYPE_TM,
            "3": PAYMENT_TYPE_TM_CK,
            "4": PAYMENT_TYPE_DTCN,
            "5": PAYMENT_TYPE_OTHER,
        }
        if search.paymentStatus == 1:
            status = "paid"
        else:
            status = "unpaid"
        if search.paymentMethod not in map_:
            method = PAYMENT_TYPE_OTHER
        else:
            method = map_[search.paymentMethod]
        payment = {
            "payment_method": method,
            "payment_method_name": search.paymentMethodName,
            "payment_status": status,
        }
        return payment

    def __get_invoice_status(self, invoice_no: str, create_date: Optional[date] = None):
        """
        issue_date

        """
        res = self.api.api_search_invoice(invoice_no=invoice_no, created_date=create_date)
        return self.__parse_invoice_status(res)

    def __get_invoice_payment_status(self, invoice_no: str, create_date: Optional[date] = None):
        res = self.api.api_search_invoice(invoice_no=invoice_no, created_date=create_date)
        return self.__parse_invoice_payment_status(res)

    def get_invoice_status(self, data: EInvoice):
        """
        issue_date

        """
        return self.__get_invoice_status(data.name, create_date=data.issue_date)

    def get_invoice_payment_status(self, data: EInvoice):
        return self.__get_invoice_payment_status(data.name, create_date=data.issue_date)

    def set_invoice_paid(self, data: EInvoice):
        self.api.api_set_invoice_paid(data.name)

    def set_invoice_unpaid(self, data: EInvoice):
        self.api.api_set_invoice_not_paid(data.name)

    def get_invoices(
        self, from_date: date, end_date: Optional[date] = None
    ) -> List[AdapterInvoiceBasicInfo]:
        """
        will return list of invoices from `from_date`
        standard format will be as follows:

        # general info
        issue_date
        invoice_no
        invoice_type
        invoice_template
        currency
        status -> original/replace/adjusted/canceled

        # buyer info
        seller_tax_code
        buyer_name
        buyer_legal_name
        buyer_address
        buyer_email_address
        buyer_phone_number
        buyer_tax_code

        # payment info
        payment_method
        payment_method_name
        payment_status

        """
        start_date = from_date
        if end_date:
            end_date = end_date
        else:
            end_date = datetime.now()
        res = self.api.api_get_invoices(
            start_date=start_date,
            end_date=end_date,
            invoice_serie=self.invoice_series,
        )
        invoices = []
        for invoice in res:
            try:
                # this is invalid invoice
                if (
                    invoice.issueDateStr == None
                    or invoice.invoiceNumber.startswith("-")
                    or invoice.invoiceNo == self.invoice_series
                ):
                    continue
                # invoices.append(invoice)
                invoice_search = self.api.api_search_invoice(invoice.invoiceNo)
                status = self.__parse_invoice_status(invoice_search)
                payment_status = self.__parse_invoice_payment_status(invoice_search)
                data = {
                    # general
                    "issue_date": invoice.issueDateStr.date(),  # date type
                    "invoice_no": invoice.invoiceNo,  # C22TNT262
                    "invoice_type": invoice.invoiceType,  # 1
                    "invoice_template": invoice.templateCode,  # '1/001'
                    "currency": invoice.currency,  # 'VND'
                    "status": status["status"],  # created/replace/adjusted/canceled
                    "transaction_id": invoice_search.transactionId,
                    "transaction_uuid": invoice_search.transactionUuid,
                    # buyer and seller
                    "buyer_name": invoice.buyerName,
                    "buyer_legal_name": invoice_search.buyerUnitName,
                    "buyer_address": invoice_search.buyerAddress,
                    "buyer_email_address": invoice_search.buyerEmailAddress,
                    "buyer_phone_number": invoice_search.buyerPhoneNumber,
                    "buyer_tax_code": invoice.buyerTaxCode,
                    "seller_tax_code": invoice.supplierTaxCode,
                    # payment
                    "payment_method": payment_status["payment_method"],
                    "payment_method_name": payment_status["payment_method_name"],
                    "payment_status": payment_status["payment_status"],
                }
                invoices.append(AdapterInvoiceBasicInfo(**data))
            except Exception as e:
                logger.error(
                    f"Error when getting data for invoice: {invoice.invoiceNo}",
                    exc_info=True,
                )
        return invoices

    def cancel_invoice(self, data: EInvoice):
        self.api.api_cancel_created_invoice(
            data.name, data.issue_date, "Cancel This Invoice From Api", datetime.now()
        )

    def send_tax_authority(self, data: EInvoice):
        self.api.api_send_tax_authority(data.name)

    def search_invoice_by_x_provider_data(
        self, data: EInvoice
    ) -> Optional[AdapterInvoiceBasicInfo]:
        try:
            provider_data = json.loads(data.x_provider_data)
            transactionID = provider_data["transactionID"]
        except:
            return None

        start_date = datetime.now() - timedelta(days=10)
        end_date = datetime.now()
        invoices = self.get_invoices(start_date, end_date)

        # matching transaction id
        for invoice in invoices:
            if invoice.transaction_id == transactionID:
                return invoice

    def send_email(self, data: EInvoice, email_addresses: List[str]) -> List[Response]:
        return self.api.api_send_email(data.name, email_addresses)
