from datetime import date, datetime
import logging
from typing import List, Optional

from .adapter_models import AdapterInvoiceBasicInfo

from .base_adapter import *
from ..viettel.sinvoice_v1 import SInvoiceApi
from ..viettel.sinvoice_v1_model import (
    Invoice_SearchInvoice,
    InvoiceTemplate as InvoiceTemplateModel,
)
from .exceptions import FeatureNotSupportException


class ViettelSInvoiceAdapter_v1(BaseAdapter):
    def build_data_for_provider(self, **conf):
        return super().build_data_for_provider(**conf)

    @property
    def api(self):
        return SInvoiceApi(
            self.tax_code, self.api_username, self.api_password, self.api_domain
        )

    def get_preview_einvoice(self, data: EInvoice):
        return super().get_preview_einvoice(data)

    def create_invoice(self, data: EInvoice):
        return super().create_invoice(data)

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

    def __get_invoice_status(self, invoice_no: str, invoice_date: date):
        """
        invoice_date

        """
        res = self.api.api_search_invoice(
            invoice_no=invoice_no, invoice_date=invoice_date
        )
        if res:
            return self.__parse_invoice_status(res)

    def __get_invoice_payment_status(self, invoice_no: str, invoice_date: date):
        res = self.api.api_search_invoice(
            invoice_no=invoice_no, invoice_date=invoice_date
        )
        if res:
            return self.__parse_invoice_payment_status(res)

    def get_invoice_status(self, data: EInvoice):
        return self.__get_invoice_status(data.name, data.issue_date)

    def get_invoice_payment_status(self, data: EInvoice):
        return self.__get_invoice_payment_status(data.name, data.issue_date)

    def set_invoice_paid(self, data: EInvoice):
        raise FeatureNotSupportException(
            "SInvoice API version 1 not support this feature"
        )

    def set_invoice_unpaid(self, data: EInvoice):
        raise FeatureNotSupportException(
            "SInvoice API version 1 not support this feature"
        )

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

    def get_invoices(
        self, from_date: date, end_date: Optional[date] = None
    ) -> List[AdapterInvoiceBasicInfo]:
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
                    invoice.issueDate == None
                    or invoice.invoiceNumber.startswith("-")
                    or invoice.invoiceNo == self.invoice_series
                ):
                    continue
                # this api v1 need created time to search invoice,
                # it is not actually a search, we manually find it base on issue date
                invoice_search = self.api.api_search_invoice(
                    invoice.invoiceNo, invoice.issueDate
                )
                data = {
                    # general
                    "issue_date": invoice.issueDate.date(),  # date type
                    "invoice_no": invoice.invoiceNo,  # C22TNT262
                    "invoice_type": invoice.invoiceType,  # 1
                    "invoice_template": invoice.templateCode,  # '1/001'
                    "currency": invoice.currency,  # 'VND'
                    "status": PROVIDER_EINVOICE_STATUS_UNKNOWN,
                    # 
                    "buyer_name": invoice.buyerName,
                    "buyer_tax_code": invoice.buyerTaxCode,
                    "seller_tax_code": invoice.supplierTaxCode,
                }
                if invoice_search:
                    status = self.__parse_invoice_status(invoice_search)
                    payment_status = self.__parse_invoice_payment_status(invoice_search)
                    data.update({
                        # general
                        "issue_date": invoice.issueDate.date(),  # date type
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
                    })
                invoices.append(AdapterInvoiceBasicInfo(**data))
            except Exception as e:
                logger.error(
                    f"Error when getting data for invoice: {invoice.invoiceNo}",
                    exc_info=True,
                )
        return invoices

    def cancel_invoice(self, data: EInvoice):
        raise FeatureNotSupportException(
            "SInvoice API version 1 not support this feature"
        )

    def send_tax_authority(self, data: EInvoice):
        raise FeatureNotSupportException(
            "SInvoice API version 1 not support this feature"
        )

    def search_invoice_by_x_provider_data(self, data: EInvoice):
        raise FeatureNotSupportException(
            "SInvoice API version 1 not support this feature"
        )


logger = logging.getLogger(__name__)
