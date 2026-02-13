from datetime import date
from typing import Optional
from pydantic import BaseModel as _BaseModel
from ..base_model import BaseModel

class AdapterInvoiceBasicInfo(BaseModel):
    issue_date: date
    invoice_no: str
    invoice_type: str
    invoice_template: str
    currency: str
    status: str

    transaction_id: Optional[str] = None
    transaction_uuid: Optional[str] = None

    buyer_name: Optional[str] = None
    buyer_legal_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_email_address: Optional[str] = None
    buyer_phone_number: Optional[str] = None
    buyer_tax_code: Optional[str] = None

    seller_tax_code: Optional[str] = None

    payment: Optional[str] = None
    payment_method: Optional[str] = None
    payment_method_name: Optional[str] = None
    payment_status: Optional[str] = None
