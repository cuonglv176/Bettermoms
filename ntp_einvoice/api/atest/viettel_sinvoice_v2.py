import base64
from datetime import datetime
import time
from ..viettel.sinvoice_v2 import SInvoiceApi
from ..viettel.sinvoice_v2_model import InvoiceTemplate


tax_code = "0100109106-718"
username = "0100109106-718"
password = "123456a@A"
sinvoice_api = SInvoiceApi(tax_code=tax_code, username=username, password=password)

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


def test_get_invoices():
    # api_get_invoices
    start_date = datetime(2022, 2, 28)
    end_date = datetime.now()
    invoices = sinvoice_api.api_get_invoices(
        start_date=start_date, end_date=end_date, invoice_serie="C22TMV"
    )
    return invoices


def test_invoice_attachment():
    template_code = "1/099"
    invoice_no = "C22TMV140"
    pdf = sinvoice_api.api_get_invoice_attachment(
        template_code=template_code, invoice_no=invoice_no, attachment_type="pdf"
    )
    zip = sinvoice_api.api_get_invoice_attachment(
        template_code=template_code, invoice_no=invoice_no, attachment_type="zip"
    )
    with open(pdf.fileName, "wb") as f:
        data = base64.b64decode(pdf.fileToBytes)
        f.write(data)

    with open(zip.fileName, "wb") as f:
        data = base64.b64decode(zip.fileToBytes)
        f.write(data)


def test_search_invoice():
    invoice_no = "C22TMV140"
    invoice = sinvoice_api.api_search_invoice(invoice_no=invoice_no)
    return invoice


def test_create_invoice_original():
    invoice_obj = InvoiceTemplate(**data)
    res = sinvoice_api.api_do_invoice("create", invoice=invoice_obj)
    invoice_no = res.result.invoiceNo
    sinvoice_api.api_wait_until_invoice_existed(invoice_no=invoice_no)
    return res


def test_cancel_invoice():
    invoice_created = test_create_invoice_original()
    invoice_no = invoice_created.result.invoiceNo

    issue_date = datetime.now()
    additional_reference_description = "Cancel Invoice"
    additional_reference_date = datetime.now()

    res = sinvoice_api.api_cancel_created_invoice(
        invoice_no=invoice_no,
        issue_date=issue_date,
        additional_reference_description=additional_reference_description,
        additional_reference_date=additional_reference_date,
    )
    return res


def test_restore_invoice():
    invoice_created = test_create_invoice_original()
    invoice_no = invoice_created.result.invoiceNo

    issue_date = datetime.now()
    additional_reference_description = "Cancel Invoice"
    additional_reference_date = datetime.now()

    res = sinvoice_api.api_cancel_created_invoice(
        invoice_no=invoice_no,
        issue_date=issue_date,
        additional_reference_description=additional_reference_description,
        additional_reference_date=additional_reference_date,
    )

    # restore
    time.sleep(1)
    res = sinvoice_api.api_restore_canceled_invoice(
        invoice_no=invoice_no, reason="Nhầm"
    )
    return res


def test_api_set_invoice_paid():
    invoice_created = test_create_invoice_original()
    invoice_no = invoice_created.result.invoiceNo
    issue_date = datetime.now()
    res = sinvoice_api.api_set_invoice_paid(invoice_no=invoice_created.result.invoiceNo)
    return res

def test_api_set_invoice_not_paid():
    invoice_created = test_create_invoice_original()
    # invoice_no = invoice_created.result.invoiceNo
    # issue_date = datetime.now()
    res = sinvoice_api.api_set_invoice_not_paid(invoice_no=invoice_created.result.invoiceNo)
    breakpoint()

def test_api_get_invoice_exchanged_attachment():
    invoice_created = test_create_invoice_original()
    # invoice_no = invoice_created.result.invoiceNo
    # issue_date = datetime.now()
    invoice_data_before = sinvoice_api.api_search_invoice(invoice_no=invoice_created.result.invoiceNo)
    res = sinvoice_api.api_get_invoice_exchanged_attachment(invoice_no=invoice_created.result.invoiceNo)
    invoice_data_after = sinvoice_api.api_search_invoice(invoice_no=invoice_created.result.invoiceNo)
    breakpoint()


def test_api_get_preview_invoice():
    global data
    invoice_obj = InvoiceTemplate(**data)
    pdf = sinvoice_api.api_get_preview_invoice(invoice=invoice_obj)
    with open(f"preview-{pdf.fileName}", "wb") as f:
        byte = base64.b64decode(pdf.fileToBytes)
        f.write(byte)

if __name__ == "__main__":
    invoices = test_get_invoices()
    # test_invoice_attachment()
    # invoice_data = test_search_invoice()
    # invoice_created = test_create_invoice_original()
    # invoice_cancel = test_cancel_invoice()
    # invoice_restore = test_restore_invoice()
    # test_api_set_invoice_paid()
    # test_api_set_invoice_not_paid()
    # test_api_get_invoice_exchanged_attachment()
    # test_api_get_preview_invoice()
    breakpoint()
