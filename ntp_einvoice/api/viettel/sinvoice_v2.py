"""
Sinvoice v2 use token authentication
"""
import logging
import re
from datetime import datetime, date, timedelta
import json
import time
from typing import List, Literal, Optional, Tuple, Union
from urllib.parse import urljoin

import requests
from requests import Response

from .sinvoice_v2_model import (
    AuthLoginResponse,
    CancelInvoiceResponse,
    GetInvoiceAttachmentResponse,
    GetInvoicesResponse,
    Invoice_GetInvoice,
    Invoice_SearchInvoice,
    InvoiceActionResponse,
    InvoiceTemplate,
    PaymentPaidResponse,
    RestoreInvoiceResponse,
    SearchInvoice,
    SendTaxAuthorityResponse,
)


DEFAULT_API_BASE_URL = "https://api-vinvoice.viettel.vn"

logger = logging.getLogger(__name__)


class SInvoiceApi:
    def __init__(
        self,
        tax_code: str,
        username: str,
        password: str,
        base_url: Optional[str] = DEFAULT_API_BASE_URL,
    ):
        self.base_url = base_url
        self.tax_code = tax_code
        self.base_headers = {"Content-Type": "application/json"}
        self.username = username
        self.password = password
        self.__expires_in: Optional[int] = None
        self.__token_time: Optional[datetime] = None
        self.__access_token: Optional[str] = None
        self.__refresh_token: Optional[str] = None
        # fmt: off

        # from doc
        self._url_auth = urljoin(self.base_url, "auth/login")
        self._url_get_invoices = urljoin(self.base_url, f"services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/getInvoices/{self.tax_code}")
        self._url_get_invoice_reprensentation_file = urljoin(self.base_url, "services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/getInvoiceRepresentationFile")
        self._url_get_invoice_file_portal = urljoin(self.base_url, "services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/getInvoiceFilePortal")
        self._url_get_invoice_file_exchanged = urljoin(self.base_url, "services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/createExchangeInvoiceFile")
        self._url_create_adjust_replace_invoice = urljoin(self.base_url, f"services/einvoiceapplication/api/InvoiceAPI/InvoiceWS/createInvoice/{self.tax_code}")
        self._url_update_invoice_payment_paid = urljoin(self.base_url, "services/einvoiceapplication/api/InvoiceAPI/InvoiceWS/updatePaymentStatus")
        self._url_update_invoice_payment_not_paid = urljoin(self.base_url, "services/einvoiceapplication/api/InvoiceAPI/InvoiceWS/cancelPaymentStatus")
        self._url_get_invoice_pdf_preview = urljoin(self.base_url, f"services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/createInvoiceDraftPreview/{self.tax_code}")
        self._url_cancel_created_invoice2 = urljoin(self.base_url, f"services/einvoiceapplication/api/InvoiceAPI/InvoiceWS/cancelTransactionInvoice")
        # from UI
        self._url_search_invoice = urljoin(self.base_url, f"services/einvoiceapplication/api/invoice/search")
        self._url_cancel_created_invoice = urljoin(self.base_url, f"services/einvoiceapplication/api/invoice/delete-invoice-released")
        self._url_restore_canceled_invoice = urljoin(self.base_url, f"services/einvoiceapplication/api/invoice/restore-invoice-deleted")
        self._url_register_invoice_file_exchanged2 = urljoin(self.base_url, "services/einvoiceapplication/api/invoice/exchange-one")
        self._url_register_invoice_gen_pdf = urljoin(self.base_url, "services/einvoiceapplication/api/invoice/gen-pdf")
        self._url_send_tax_authority = urljoin(self.base_url, f"services/einvoiceapplication/api/invoice/sent-invoice-to-cqt")
        self._url_send_email_customer = urljoin(self.base_url, f"services/einvoiceapplication/api/email/send-email-customer")

        # fmt: on

    def get_header(self, **kwargs):
        headers = self.base_headers.copy()
        headers.update(**kwargs)
        return headers

    def get_header_auth(self, **kwargs):
        headers = self.get_header(
            Cookie=f"access_token={self.__access_token}", **kwargs
        )
        return headers

    def get_auth(self):
        return {
            "username": self.username,
            "password": self.password,
        }

    @property
    def is_token_expired(self):
        if self.__expires_in is None:
            return True
        if self.__token_time is None:
            return True
        if (datetime.now() - self.__token_time).seconds >= self.__expires_in:
            return True
        return False

    def __update_token(self):
        if self.is_token_expired:
            res = requests.post(
                self._url_auth, headers=self.get_header(), json=self.get_auth()
            )
            auth_login = AuthLoginResponse(**res.json())
            self.__access_token = auth_login.access_token
            self.__refresh_token = auth_login.refresh_token
            self.__expires_in = auth_login.expires_in
            self.__token_time = datetime.now()

    def api_get_invoices(
        self, start_date: Union[datetime, bool, None], end_date: Union[datetime, bool, None], invoice_serie: str
    ) -> List[Invoice_GetInvoice]:

        # --- FIX START: Handle False/None from Odoo ---
        if not start_date or isinstance(start_date, bool):
            start_date = datetime.now() - timedelta(days=60)

        if not end_date or isinstance(end_date, bool):
            end_date = datetime.now()
        # --- FIX END ---

        row_per_page = 50
        data = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "rowPerPage": row_per_page,
            "invoiceSeri": invoice_serie,
        }
        page_no = 1
        invoices: List[Invoice_GetInvoice] = []

        while True:
            self.__update_token()
            #
            _data = data.copy()
            _data["pageNum"] = page_no
            res = requests.post(
                self._url_get_invoices, json=_data, headers=self.get_header_auth()
            )

            # Add basic error handling for non-JSON responses
            try:
                json_response = res.json()
            except Exception:
                logger.error(f"Invalid JSON response: {res.text}")
                break

            invoices_data = GetInvoicesResponse(**json_response)

            if invoices_data.invoices:
                invoices += invoices_data.invoices

            # Safe division
            total_rows = invoices_data.totalRows or 0
            if total_rows == 0:
                break

            total_page = int(total_rows / row_per_page) + (
                1 if total_rows % row_per_page != 0 else 0
            )
            if total_page == 0:
                break
            if page_no >= total_page:
                break
            page_no += 1

        return invoices

    def api_get_invoice_attachment(
        self,
        template_code: str,
        invoice_no: str,
        attachment_type: Literal["pdf", "zip"],
    ) -> GetInvoiceAttachmentResponse:
        data = {
            "supplierTaxCode": self.tax_code,
            "templateCode": template_code,
            "invoiceNo": invoice_no,
            "fileType": attachment_type,
        }
        self.__update_token()
        res = requests.post(
            self._url_get_invoice_reprensentation_file,
            json=data,
            headers=self.get_header_auth(),
        )
        attachment_response = GetInvoiceAttachmentResponse(**res.json())
        return attachment_response

    def api_search_invoice(self, invoice_no: str, created_date: Optional[date] = None) -> Invoice_SearchInvoice:
        # Fix 2023-07-13 vincoice require date when search invoice
        if created_date:
            from_date = created_date - timedelta(days=10)
            to_date = created_date + timedelta(days=10)
        else:
            # Improved regex to handle any series letter (C, K, etc.)
            issue_year = re.findall(r"[A-Z](\d{2}).+", invoice_no)
            if issue_year:
                issue_year = 2000 + int(issue_year[0])
            else:
                # Fallback to current year instead of crashing if regex fails
                issue_year = datetime.now().year
                logger.warning(f"Could not parse year from invoice {invoice_no}, defaulting to {issue_year}")

            # hard code base on the invoice format _YY___***
            from_date = date(year=issue_year, month=1, day=1)
            to_date = date(year=issue_year, month=12, day=31)
        params = {
            "invoiceNo.equals": invoice_no,
            "invoiceStatus.equals": 1,
            "createdDate.greaterThanOrEqual": f"{from_date.strftime('%Y-%m-%d')}T00:00:00.000Z",
            "createdDate.lessThanOrEqual": f"{to_date.strftime('%Y-%m-%d')}T23:59:59.000Z",
            "dateType.equals": "0"
        }

        self.__update_token()
        res = requests.get(
            self._url_search_invoice,
            params=params,
            headers=self.get_header_auth(),
        )
        search_invoice_response = SearchInvoice(**res.json())

        if search_invoice_response.data.content:
            return search_invoice_response.data.content[0]
        else:
            raise ValueError(f"Invoice {invoice_no} not found")

    def api_do_invoice(
        self,
        action: Literal["create", "adjust", "replace"],
        invoice: InvoiceTemplate,
    ) -> InvoiceActionResponse:
        data = invoice.dict(exclude_none=True)
        self.__update_token()
        data = json.loads(json.dumps(data))
        res = requests.post(
            self._url_create_adjust_replace_invoice,
            json=data,
            headers=self.get_header_auth(),
        )
        logger.info(res.text)
        # TODO: when invoice is created, it may take time to search or get info from server of sinvoice
        # TODO: need to find a way to avoid sleep
        invoice_action_response = InvoiceActionResponse(**res.json())
        return invoice_action_response

    def api_wait_until_invoice_existed(self, invoice_no, timeout=10):
        start_time = time.time()
        invoice_data = None
        while True:
            try:
                invoice_data = self.api_search_invoice(invoice_no=invoice_no)
                break
            except Exception as e:
                if time.time() - start_time > timeout:
                    break
                time.sleep(1)
        if not invoice_data:
            return False
        return True

    def api_cancel_created_invoice(
        self,
        invoice_no,
        issue_date: datetime,
        additional_reference_description: str,
        additional_reference_date: datetime,
    ):
        """take this from sinvoice webUI"""
        invoice_data = self.api_search_invoice(invoice_no=invoice_no)
        data = {
            "additionalReferenceDate": additional_reference_date.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),  # "2022-03-22T17:00:00.000Z",
            "additionalReferenceDesc": additional_reference_description,
            "agreementFileName": None,
            "agreementFilePath": None,
            "docDeal": None,
            "id": invoice_data.id,
            "reason": additional_reference_description,
        }
        res = requests.put(
            self._url_cancel_created_invoice, json=data, headers=self.get_header_auth()
        )
        cancel_response = CancelInvoiceResponse(**res.json())
        return cancel_response

    def api_restore_canceled_invoice(self, invoice_no: str, reason: str):
        invoice_data = self.api_search_invoice(invoice_no=invoice_no)
        data = {
            "idInvoice": invoice_data.id,
            "reason": reason,
        }
        res = requests.put(
            self._url_restore_canceled_invoice,
            params=data,
            headers=self.get_header_auth(),
        )
        restore_invoice = RestoreInvoiceResponse(**res.json())
        return restore_invoice

    def api_set_invoice_paid(self, invoice_no):
        invoice_data = self.api_search_invoice(invoice_no=invoice_no)
        data = {
            "supplierTaxCode": self.tax_code,
            "templateCode": invoice_data.templateCode,
            "invoiceNo": invoice_data.invoiceNo,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        res = requests.post(
            self._url_update_invoice_payment_paid,
            data=data,
            headers=self.get_header_auth(**headers),
        )
        logger.info(res.text)
        payment_paid_response = PaymentPaidResponse(**res.json())
        return payment_paid_response

    def api_set_invoice_not_paid(self, invoice_no):
        invoice_data = self.api_search_invoice(invoice_no=invoice_no)
        data = {
            "supplierTaxCode": self.tax_code,
            # "templateCode": invoice_data.templateCode,
            "invoiceNo": invoice_data.invoiceNo,
            "strIssueDate": str(int(invoice_data.issueDate.strftime("%s")) * 1000),
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        res = requests.post(
            self._url_update_invoice_payment_not_paid,
            data=data,
            headers=self.get_header_auth(**headers),
        )
        logger.info(res.text)

    def __is_invoice_exchanged_registered(self, invoice_no):
        invoice_data = self.api_search_invoice(invoice_no=invoice_no)
        if invoice_data.actionInvoiceDTO and invoice_data.actionInvoiceDTO.downloadExchange == 1:
            return True
        return False

    def api_get_invoice_exchanged_attachment(self, invoice_no):
        invoice_data = self.api_search_invoice(invoice_no=invoice_no)
        if self.__is_invoice_exchanged_registered(invoice_no=invoice_no):
            params = {"id": invoice_data.id, "exchange": True}
            res = requests.get(
                self._url_register_invoice_gen_pdf,
                params=params,
                headers=self.get_header_auth(),
            )
        else:
            params = {"id": invoice_data.id}
            res = requests.get(
                self._url_register_invoice_file_exchanged2,
                params=params,
                headers=self.get_header_auth(),
            )
        logger.info(res.text)
        return res

    def api_get_preview_invoice(
        self, invoice: InvoiceTemplate
    ) -> Tuple[Response, Optional[GetInvoiceAttachmentResponse]]:
        data = invoice.dict(exclude_none=True)
        self.__update_token()
        data = json.loads(json.dumps(data))
        res = requests.post(
            self._url_get_invoice_pdf_preview,
            json=data,
            headers=self.get_header_auth(),
        )
        # TODO: when invoice is created, it may take time to search or get info from server of sinvoice
        # TODO: need to find a way to avoid sleep
        try:
            attachement_response = GetInvoiceAttachmentResponse(**res.json())
            return res, attachement_response
        except Exception as e:
            logger.error(res.text, exc_info=True)
            return res, None

    def api_send_tax_authority(self, invoice_no) -> Optional[SendTaxAuthorityResponse]:
        invoice_data = self.api_search_invoice(invoice_no)
        if invoice_data.id:
            if invoice_data.errorCode not in [
                "INVOICE_HAS_CODE_SENT",
                "INVOICE_HAS_CODE_APPROVED",
            ]:
                self.__update_token()
                res = requests.put(
                    self._url_send_tax_authority,
                    data=str(invoice_data.id),
                    headers=self.get_header_auth(),
                )
                return SendTaxAuthorityResponse(**res.json())
            else:
                logger.info(
                    f"invoice {invoice_no}: current invoice errorCode = {invoice_data.errorCode}"
                )
        return None

    def api_send_email(
        self, invoice_no, email_address: Union[str, List[str]]
    ) -> List[Response]:
        return_responses = []
        if type(email_address) == str:
            email_address = [email_address]
        invoice_data = self.api_search_invoice(invoice_no)
        if invoice_data.id:
            self.__update_token()
            for email in email_address:
                data = {
                    "buyerEmailAddress": email,
                    "id": invoice_data.id,
                }
                res = requests.post(
                    self._url_send_email_customer,
                    json=data,
                    headers=self.get_header_auth(),
                )
                return_responses.append(res)
        return return_responses


__all__ = ["SInvoiceApi"]


if __name__ == "__main__":
    tax_code = "0100109106-718"
    username = "0100109106-718"
    password = "123456a@A"
    sinvoice_api = SInvoiceApi(tax_code=tax_code, username=username, password=password)

    # api_get_invoices
    start_date = datetime(2022, 2, 28)
    end_date = datetime.now()
    invoices = sinvoice_api.api_get_invoices(
        start_date=start_date, end_date=end_date, invoice_serie="C22TMV"
    )
    breakpoint()

    # api_get_invoice_attachment
    template_code = "1/099"
    invoice_no = "C22TMV140"
    pdf = sinvoice_api.api_get_invoice_attachment(
        template_code=template_code, invoice_no=invoice_no, attachment_type="pdf"
    )
    zip = sinvoice_api.api_get_invoice_attachment(
        template_code=template_code, invoice_no=invoice_no, attachment_type="zip"
    )

    # api_search_invoice
    invoice = sinvoice_api.api_search_invoice(invoice_no=invoice_no)

    # create invoice
    data = {
        "generalInvoiceInfo": {
            "invoiceType": "1",
            "templateCode": "1/001",
            "invoiceSeries": "K22TFO",
            "currencyCode": "VND",
            "adjustmentType": 1,
            "paymentStatus": False,
        },
        "buyerInfo": {
            "buyerName": "ADM21 VINA CO.,LTD",
            "buyerTaxCode": "",
            "buyerAddressLine": "Lô C5, Khu công nghiệp Khánh Phú - Xã Khánh Phú - Huyện Yên Khánh",
            "buyerEmail": "",
            "buyerBankName": "",
            "buyerBankAccount": "",
        },
        "sellerInfo": {},
        "payments": [
            {"paymentMethodName": "TM/CK"},
        ],
        "itemInfo": [
            {
                "lineNumber": 1,
                "itemName": "BRUNT",
                "itemCode": "ATAKR1601",
                "unitCode": "PIECE-CODE",
                "unitName": "Piece",
                "quantity": 1.0,
                "unitPrice": 1000000.0,
                "itemTotalAmountWithoutTax": 1000000.0,
                "taxPercentage": 8,
                "taxAmount": 80000.0,
                "itemTotalAmountWithTax": 0.0,
            }
        ],
        "summarizeInfo": {
            "sumOfTotalLineAmountWithoutTax": 1000000,
            "totalAmountWithoutTax": 1000000,
            "totalTaxAmount": 80000,
            "totalAmountWithTax": 1080000,
            "totalAmountWithTaxInWords": "Một triệu tám mươi nghìn đồng chẵn.",
            "taxPercentage": "8",
            "discountAmount": 0.0,
        },
        "taxBreakdowns": [
            {"taxPercentage": "8", "taxableAmount": 1000000, "taxAmount": 80000}
        ],
    }
    data.pop("sellerInfo")
    invoice_obj = InvoiceTemplate(**data)
    res = sinvoice_api.api_do_invoice("create", invoice=invoice_obj)
    invoice_no = res.result.invoiceNo

    sinvoice_api.api_wait_until_invoice_existed(invoice_no=invoice_no)

    issue_date = datetime.now()
    additional_reference_description = "Cancel Invoice"
    additional_reference_date = datetime.now()
    res = sinvoice_api.api_cancel_created_invoice(
        invoice_no=invoice_no,
        issue_date=issue_date,
        additional_reference_description=additional_reference_description,
        additional_reference_date=additional_reference_date,
    )

    res = sinvoice_api.api_restore_canceled_invoice(
        invoice_no=invoice_no, reason="Nhầm"
    )

    # adjust invoice case

    breakpoint()