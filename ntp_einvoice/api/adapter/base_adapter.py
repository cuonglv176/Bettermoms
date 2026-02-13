from datetime import date
from typing import List

from requests import Response

from .adapter_models import AdapterInvoiceBasicInfo
from ...models.einvoice import EInvoice
from ...models.einvoice_line import EInvoiceLine
from ...models.einvoice_template import EInvoiceTemplate
from ...utils.const import *


class BaseAdapter:
    def __init__(self, template: EInvoiceTemplate):
        self.template = template
        self.api_domain = template.api_domain
        self.api_username = template.api_username
        self.api_password = template.api_password
        self.tax_code = template.tax_code
        self.invoice_template = template.invoice_template
        self.invoice_template_type = template.invoice_template_type
        self.invoice_series = template.invoice_series

    def build_data_for_provider(self, **conf):
        pass

    def get_preview_einvoice(self, data: EInvoice):
        raise NotImplementedError("Not Implemented")

    def create_invoice(self, data: EInvoice):
        raise NotImplementedError("Not Implemented")

    def get_invoice_status(self, data: EInvoice):
        raise NotImplementedError("Not Implemented")

    def get_invoice_attachment_pdf(self, data: EInvoice):
        raise NotImplementedError("Not Implemented")

    def get_invoice_attachment_xml(self, data: EInvoice):
        raise NotImplementedError("Not Implemented")

    def get_invoice_status(self, data: EInvoice):
        raise NotImplementedError()

    def get_invoice_payment_status(self, data: EInvoice):
        raise NotImplementedError()

    def set_invoice_paid(self, data: EInvoice):
        raise NotImplementedError()

    def set_invoice_unpaid(self, data: EInvoice):
        raise NotImplementedError()

    def get_invoices(self, from_date: date) -> List[AdapterInvoiceBasicInfo]:
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
        buyer_tax_code

        # payment info
        payment_method
        payment_status

        """
        raise NotImplementedError()

    def cancel_invoice(self, data: EInvoice):
        raise NotImplementedError()

    def send_tax_authority(self, data: EInvoice):
        raise NotImplementedError()

    def search_invoice_by_x_provider_data(self, data: EInvoice):
        """it is stored in x_provider_data in odoo's einvoice object"""
        raise NotImplementedError()

    def send_email(self, data: EInvoice, email_addresses: List[str]) -> List[Response]:
        raise NotImplementedError()

    @property
    def api(self):
        raise NotImplementedError("Not Implemented")


__all__ = [
    "BaseAdapter",
    "EInvoice",
    "EInvoiceLine",
    "EInvoiceTemplate",
    #
    "PAYMENT_TYPE_CK",
    "PAYMENT_TYPE_TM",
    "PAYMENT_TYPE_TM_CK",
    "PAYMENT_TYPE_DTCN",
    "PAYMENT_TYPE_OTHER",
    "PAYMENT_STATUS_NOT_PAID_YET",
    "PAYMENT_STATUS_PAID",
    #
    "BUYER_NOT_NEED_INVOICE",
    "BUYER_INDIVIDUAL",
    "BUYER_COMPANY",
    #
    "PROVIDER_EINVOICE_STATUS_DRAFT",
    "PROVIDER_EINVOICE_STATUS_REQUESTED",
    "PROVIDER_EINVOICE_STATUS_ISSUED",
    "PROVIDER_EINVOICE_STATUS_REPLACE",
    "PROVIDER_EINVOICE_STATUS_ADJUST",
    "PROVIDER_EINVOICE_STATUS_CANCELED",
    "PROVIDER_EINVOICE_STATUS_UNKNOWN"
]
