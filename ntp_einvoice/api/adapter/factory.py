from datetime import date
from typing import Dict, List, Literal, Optional

from requests import Response

from .adapter_models import AdapterInvoiceBasicInfo
from .base_adapter import *
from .viettel_sinvoice_v1 import ViettelSInvoiceAdapter_v1
from .viettel_sinvoice_v2 import ViettelSInvoiceAdapter_v2
from .exceptions import FeatureNotSupportException


factory_db = {
    "sinvoice_v1": ViettelSInvoiceAdapter_v1,
    "sinvoice_v2": ViettelSInvoiceAdapter_v2,
}


class EInvoiceFactory:
    """
    Factory class to work with multiple einvoice provider
    It will generatte adapter object to interwork with odoo models and provider api to

    - preview invoice
    - generate invoice
    - ... other tasks

    """

    FEATURE_NOT_SUPPORT_EXCEPTION = FeatureNotSupportException

    @classmethod
    def from_provider(cls, template: EInvoiceTemplate):
        return cls(adapter=factory_db[template.provider](template=template))

    def __init__(self, adapter: BaseAdapter):
        self._adapter = adapter

    def get_preview_einvoice(self, data: EInvoice) -> dict:
        res = self._adapter.get_preview_einvoice(data)
        return res

    def create_invoice(self, data: EInvoice) -> dict:
        res = self._adapter.create_invoice(data)
        return {
            "invoice_no": res["invoice_no"],
            "provider_data": res["provider_data"],
        }

    def get_invoice_attachment_pdf(self, data: EInvoice) -> dict:
        res = self._adapter.get_invoice_attachment_pdf(data)
        return res

    def get_invoice_attachment_xml(self, data: EInvoice) -> dict:
        res = self._adapter.get_invoice_attachment_xml(data)
        return res

    def get_invoice_status(self, data: EInvoice) -> Optional[dict]:
        return self._adapter.get_invoice_status(data)

    def get_invoice_payment_status(self, data: EInvoice) -> Optional[Literal["paid", "unpaid"]]:
        return self._adapter.get_invoice_payment_status(data)

    def set_invoice_paid(self, data: EInvoice):
        return self._adapter.set_invoice_paid(data)

    def set_invoice_unpaid(self, data: EInvoice):
        return self._adapter.set_invoice_unpaid(data)

    def get_invoices(
        self, from_date: date, end_date: Optional[date] = None
    ) -> List[AdapterInvoiceBasicInfo]:
        """ """
        return self._adapter.get_invoices(from_date, end_date)

    def cancel_invoice(self, data: EInvoice):
        return self._adapter.cancel_invoice(data)

    def send_tax_authority(self, data: EInvoice):
        return self._adapter.send_tax_authority(data)

    def search_invoice_by_x_provider_data(
        self, data: EInvoice
    ) -> Optional[AdapterInvoiceBasicInfo]:
        return self._adapter.search_invoice_by_x_provider_data(data)

    def send_email(self, data: EInvoice, email_addresses: List[str]) -> List[Response]:
        return self._adapter.send_email(data, email_addresses)
