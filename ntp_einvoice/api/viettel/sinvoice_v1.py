from datetime import date, datetime, timedelta
import logging
from typing import List, Literal, Optional
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

DEFAULT_API_BASE_URL = "https://api-sinvoice.viettel.vn"


from .sinvoice_v1_model import (
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
    SendTaxAuthorityResponse,
    # for v1
    InvoiceDataControlResponse,
)


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
        self.base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.username = username
        self.password = password

        # fmt: off
        # from doc
        self._url_get_invoices = urljoin(self.base_url, f"InvoiceAPI/InvoiceUtilsWS/getInvoices/{self.tax_code}")
        self._url_get_invoice_reprensentation_file = urljoin(self.base_url, "InvoiceAPI/InvoiceUtilsWS/getInvoiceRepresentationFile")
        self._url_get_invoice_list_by_date_range = urljoin(self.base_url, "InvoiceAPI/InvoiceUtilsWS/getListInvoiceDataControl")
        # fmt: on

    def get_header(self, **kwargs):
        headers = self.base_headers.copy()
        headers.update(**kwargs)
        return headers

    def get_header_auth(self, **kwargs):
        headers = self.get_header(**kwargs)
        return headers

    def api_get_invoices(
        self, start_date: datetime, end_date: datetime, invoice_serie: str
    ):
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
            #
            _data = data.copy()
            _data["pageNum"] = page_no
            res = requests.post(
                self._url_get_invoices,
                json=_data,
                headers=self.get_header_auth(),
                auth=HTTPBasicAuth(self.username, self.password),
            )
            invoices_data = GetInvoicesResponse(**res.json())
            invoices += invoices_data.invoices
            total_page = int(invoices_data.totalRows / row_per_page) + (
                1 if invoices_data.totalRows % row_per_page != 0 else 0
            )
            if total_page == 0:
                break
            if page_no == total_page:
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
        res = requests.post(
            self._url_get_invoice_reprensentation_file,
            json=data,
            headers=self.get_header_auth(),
            auth=HTTPBasicAuth(self.username, self.password),
        )
        attachment_response = GetInvoiceAttachmentResponse(**res.json())
        if not attachment_response.fileName.endswith(f".{attachment_type}"):
            attachment_response.fileName += f".{attachment_type}"
        return attachment_response

    def api_search_invoice(self, invoice_no: str, invoice_date: date) -> Optional[Invoice_SearchInvoice]:
        data = {
            "supplierTaxCode": self.tax_code,
            "fromDate": date.strftime(invoice_date, "%d/%m/%Y"),
            "toDate": date.strftime(invoice_date, "%d/%m/%Y"),
        }
        res = requests.post(
            self._url_get_invoice_list_by_date_range,
            json=data,
            headers=self.get_header_auth(),
            auth=HTTPBasicAuth(self.username, self.password),
        )
        try:
            dco = InvoiceDataControlResponse(**res.json())
            for invoice in dco.lstInvoiceBO:
                if invoice.invoiceNo == invoice_no:
                    return invoice
        except Exception as e:
            logger.error(e, exc_info=True)
            return None


if __name__ == "__main__":
    api = SInvoiceApi("0108951191", "0108951191", "Diep@123")
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2022, 3, 1)
    invoices = api.api_get_invoices(start_date, end_date, "C21TNT")
    invoice = invoices[0]
    pdf = api.api_get_invoice_attachment(invoice.templateCode, invoice.invoiceNo, 'pdf')

    inv = api.api_search_invoice("C22TNT166", date.fromtimestamp(1645608396000/1000))
    breakpoint()
