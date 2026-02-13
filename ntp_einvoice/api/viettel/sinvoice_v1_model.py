from datetime import date, datetime
from enum import Enum
from typing import Any, List, Literal, Optional
from pydantic import Field
from pydantic import BaseModel as _BaseModel
from ..base_model import BaseModel

# {
#     "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX25hbWUiOiIwMTAwMTA5MTA2LTcxOCIsInNjb3BlIjpbIm9wZW5pZCJdLCJleHAiOjE2NDgwNTM5NDQsInR5cGUiOjEsImlhdCI6MTY0ODA1MzY0NCwiaW52b2ljZV9jbHVzdGVyIjoiY2x1c3RlcjQiLCJhdXRob3JpdGllcyI6WyJST0xFX1VTRVIiXSwianRpIjoiM2ZkZmJlYjYtODMxMS00NWMzLWEwMGEtNmRkYmNmMTkxYzNhIiwiY2xpZW50X2lkIjoid2ViX2FwcCJ9.IKrmRNYUZWH0QAhsSLGzZlIasogHMV2GSNVGv21AUZvZ2Alt_pXBSQq0Ri4Gv8qkYpW8bDIp3993OOwKOwiIapl6j-GGR0wP3Kwd6go4tG0ZkYzZp7xCd285AQ2urP2OtEp6ZcN5zKUOw6J7XhCyd9J1qxhs1BXXQ91XUYx4Mih4LMJHcXMkcVQO_ExG9cMmjgDn_UKOO_pqZ97sr6f3sq0pCAAe3LKo72clKVChRHE_eswrUAXt7baQagqCe9MlCmDDXS2PRF3VPIdzbSc6iAde8U6E6hRGr13CRukkxGZod2Kl19qxythazXy9Renhlec0uzGvlRQQxmHbNwLsBA",
#     "token_type": "bearer",
#     "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX25hbWUiOiIwMTAwMTA5MTA2LTcxOCIsInNjb3BlIjpbIm9wZW5pZCJdLCJhdGkiOiIzZmRmYmViNi04MzExLTQ1YzMtYTAwYS02ZGRiY2YxOTFjM2EiLCJleHAiOjE2NDg2NTg0NDQsInR5cGUiOjEsImlhdCI6MTY0ODA1MzY0NCwiaW52b2ljZV9jbHVzdGVyIjoiY2x1c3RlcjQiLCJhdXRob3JpdGllcyI6WyJST0xFX1VTRVIiXSwianRpIjoiNTU1ZjhmYTQtYzdjOC00ZGJhLTg5ZTUtOTZkMzQ0YjI5NjM0IiwiY2xpZW50X2lkIjoid2ViX2FwcCJ9.hQyBIMV7qfhPhWattZYvuIFk5Zuco7di0nq3OUSCnimzHceDsH4akMCVJQxQ5qapd5DiPOBq4Dlk2cnF1xBjyD1Dw3FBhxkKzjS08HWi0AqIlIQ7chAKDykh_Vo3iVPE0sTeNCwjGPhiAZEcVGtiTp_-OcYKAeFIbdEsBoOtN1gCtvLWi5Ugu8tuWSrYfUgjF8LKvjRrnkE2JOhLDqd_PX1GRQwHVpnaTl-QMUDo14SwfuCcu8LTcGWsWq6tz8idWr5abibCs_hwRzUEoMeel2L9F6-XPRbgBD6icURvaNS7zL4DN6HAgM_X-Vf7MXX5C7158zpw3PetFOXiH8_ECg",
#     "expires_in": 298,
#     "scope": "openid",
#     "iat": 1648053644,
#     "invoice_cluster": "cluster4",
#     "type": 1,
#     "jti": "3fdfbeb6-8311-45c3-a00a-6ddbcf191c3a"
# }

# login
class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    refresh_token: str
    expires_in: int
    scope: str
    iat: int
    invoice_cluster: str
    type: int
    jti: str


# api_get_invoices
class Invoice_GetInvoice(BaseModel):
    invoiceId: int
    invoiceType: str
    adjustmentType: str
    templateCode: str
    invoiceSeri: str
    invoiceNumber: str
    invoiceNo: str
    currency: str
    total: Optional[float] = None  # sinvoice v1
    issueDate: Optional[datetime] = None
    issueDateStr: Optional[datetime] = None
    state: Optional[int] = None
    requestDate: Optional[Any] = None
    description: Optional[Any] = None
    buyerIdNo: Optional[Any] = None
    stateCode: Optional[int] = None
    subscriberNumber: Optional[Any] = None
    paymentStatus: Optional[int] = None
    viewStatus: Optional[Any] = None
    downloadStatus: Optional[Any] = None
    exchangeStatus: Optional[int] = None
    numOfExchange: Optional[Any] = None
    createTime: Optional[Any] = None
    contractId: Optional[Any] = None
    contractNo: Optional[Any] = None
    supplierTaxCode: str
    buyerTaxCode: Optional[Any] = None
    totalBeforeTax: Optional[float] = None  # sinvoice v1
    taxAmount: Optional[float] = None  # sinvoice v1
    taxRate: Optional[Any] = None
    paymentMethod: Optional[str] = None
    paymentTime: Optional[Any] = None
    customerId: Optional[Any] = None
    no: Optional[Any] = None
    paymentStatusName: Optional[str] = None
    buyerName: Optional[str] = None


class GetInvoicesResponse(BaseModel):
    errorCode: Literal[None]
    description: Optional[str] = None
    totalRows: int = Field(..., alias='totalRow')
    invoices: List[Invoice_GetInvoice]


# api_get_invoice_attachment
class GetInvoiceAttachmentResponse(BaseModel):
    errorCode: Optional[Literal[200]] = None
    description: Optional[str] = None
    fileToBytes: str
    paymentStatus: bool
    fileName: str


# invoice to create/replace/adjust
class AdjustmentTypeEnum(int, Enum):
    ORIGINAL_INVOICE = 1
    REPLACE_INVOICE = 3
    ADJUSTMENT_INVOICE = 5


class AdjustmentInvoiceTypeEnum(str, Enum):
    INVOICE_ADJUST_MONEY = "1"
    INVOICE_ADJUST_INFO = "3"


class GeneralInvoiceInfo(BaseModel):
    invoiceType: str
    templateCode: str
    invoiceSeries: str
    currencyCode: str
    adjustmentType: Optional[AdjustmentTypeEnum] = None
    adjustmentInvoiceType: Optional[AdjustmentInvoiceTypeEnum] = None
    originalInvoiceId: Optional[str] = None
    originalInvoiceIssueDate: Optional[str] = None
    additionalReferenceDesc: Optional[str] = None
    additionalReferenceDate: Optional[str] = None
    paymentStatus: Optional[bool] = False
    cusGetInvoiceRight: Optional[bool] = True
    transactionUuid: Optional[str] = None

class BuyerNotGetInvoiceEnum(int, Enum):
    NO = 0
    YES = 1


class SellerInfo(BaseModel):
    sellerLegalName: str
    sellerTaxCode: str
    sellerAddressLine: str
    sellerPhoneNumer: Optional[str] = None
    sellerFaxNumber: Optional[str] = None
    sellerEmail: Optional[str] = None
    sellerBankName: Optional[str] = None
    sellerBankAccount: Optional[str] = None
    sellerDistrictName: Optional[str] = None
    sellerCityName: Optional[str] = None
    sellerCountryCode: Optional[str] = None
    sellerWebsite: Optional[str] = None


class BuyerInfo(BaseModel):
    buyerName: Optional[str] = None
    buyerLegalName: Optional[str] = None
    buyerTaxCode: Optional[str] = None
    buyerAddressLine: Optional[str] = None
    buyerPostalCode: Optional[str] = None
    buyerDistrictName: Optional[str] = None
    buyerCityName: Optional[str] = None
    buyerCountryCode: Optional[str] = None
    buyerPhoneNumber: Optional[str] = None
    buyerFaxNumber: Optional[str] = None
    buyerEmail: Optional[str] = None
    buyerBankName: Optional[str] = None
    buyerBankAccount: Optional[str] = None
    buyerIdType: Optional[str] = None
    buyerIdNo: Optional[str] = None
    buyerCode: Optional[str] = None
    buyerBirthDay: Optional[str] = None
    # buyerNotGetInvoice: Optional[BuyerNotGetInvoiceEnum] = False


class PaymentMethodEnum(str, Enum):
    TM = "1"
    CK = "2"
    TM_CK = "3"
    DTCN = "4"
    KHAC = "5"


class Payment(BaseModel):
    paymentMethod: Optional[PaymentMethodEnum] = PaymentMethodEnum.TM_CK
    paymentMethodName: str


class ItemInfo_SelectionEnum(int, Enum):
    PRODUCT = 1
    NOTE = 2
    DISCOUNT = 3
    TABLE_LIST = 4
    OTHER_COST = 5
    PROMOTION = 6


class ItemInfo(BaseModel):
    """
    tax here is excise tax not vat tax
    """
    lineNumber: Optional[int] = None
    selection: Optional[ItemInfo_SelectionEnum] = None
    itemCode: str
    itemName: str
    unitCode: str
    unitName: str
    unitPrice: float
    quantity: float
    itemTotalAmountWithoutTax: float
    taxPercentage: float
    taxAmount: float
    isIncreaseItem: Optional[bool] = None
    itemNote: Optional[str] = None
    discount: Optional[float] = None
    discount2: Optional[float] = None
    itemDiscount: Optional[float] = None
    itemTotalAmountAfterDiscount: Optional[float] = None
    itemTotalAmountWithTax: Optional[float] = None


class TaxBreakDown(BaseModel):
    taxPercentage: float
    taxableAmount: float
    taxAmount: float
    taxableAmountPos: Optional[float] = None
    taxAmountPos: Optional[float] = None
    taxExemptionReason: Optional[str] = None


class SummarizeInfo(BaseModel):
    sumOfTotalLineAmountWithoutTax: float
    totalAmountWithoutTax: float
    totalTaxAmount: float
    totalAmountWithTax: float
    totalAmountWithTaxFrn: Optional[bool] = None
    totalAmountWithTaxInWords: Optional[str] = None
    isTotalAmountPos: Optional[bool] = None
    isTotalTaxAmountPos: Optional[bool] = None
    isTotalAmtWithoutTaxPos: Optional[bool] = None
    discountAmount: float
    settlementDiscountAmount: Optional[float] = None
    isDiscountAmtPos: Optional[bool] = None
    taxPercentage: float


class InvoiceTemplate(BaseModel):
    generalInvoiceInfo: GeneralInvoiceInfo
    buyerInfo: BuyerInfo
    sellerInfo: Optional[SellerInfo] = {}
    payments: List[Payment]
    itemInfo: List[ItemInfo]
    summarizeInfo: SummarizeInfo
    taxBreakdowns: List[TaxBreakDown]


class InvoiceActionResult(BaseModel):
    supplierTaxCode: str
    invoiceNo: str
    transactionID: Optional[str] = None
    reservationCode: str


class InvoiceActionResponse(BaseModel):
    errorCode: Optional[int] = None
    description: Optional[str] = None
    result: InvoiceActionResult


# cancel invoice like from web UI
class CancelInvoiceResponse(BaseModel):
    code: int
    message: Literal['OK', "ok", 'Ok']
    data: bool

class RestoreInvoiceResponse(CancelInvoiceResponse):
    pass


# payment Paid
class PaymentPaidResponse(BaseModel):
    errorCode: Optional[int] = None
    description: Optional[str] = None
    result: bool
    paymentTime: datetime
    paymentMethod: str


# send tax authorities
class SendTaxAuthorityData(BaseModel):
    invoiceNo: str
    reservationCode: Any
    tenantTaxCode: Any
    message: Any
    issueDate: Any
    errorCode: Any


class SendTaxAuthorityResponse(BaseModel):
    code: int
    message: str
    data: SendTaxAuthorityData


# ONLY FOR V1

class Invoice_SearchInvoice(BaseModel):
    invoiceId: int
    invoiceRequestId: int
    transactionId: str
    invoiceType: str
    adjustmentType: str
    adjustmentInvoiceType: Any
    supplierTaxCode: str
    templateCode: str
    username: str
    password: Any
    backOffice: Any
    issueDate: datetime
    invoiceSeri: str
    invoiceNumber: int
    invoiceNo: str
    buyerIdType: Optional[str]
    buyerIdNo: Optional[str]
    buyerTaxCode: Optional[str]
    buyerName: Optional[str]
    buyerAddress: str
    contractNo: Any
    subscriberNumber: Any
    subscriberId: Any
    totalBeforeTax: Optional[int] = None
    taxAmount: Optional[int] = None
    discount: Optional[int] = None
    total: Optional[int] = None
    invoicePath: Any
    folderId: int
    filePath: str
    fileName: str
    instanceFilePath: Any
    instanceFileName: Any
    exchangeFilePath: Any
    exchangeFileName: Any
    backofficeRequestTime: Any
    responseBackofficeTime: int
    lastUpdateTime: int
    tempFilePath: str
    tempFileName: str
    errorCode: Optional[str]
    description: Any
    currency: str
    reservationCode: str
    signatureValue: Any
    digestValue: Any
    createTime: int
    stateCode: str
    status: int
    numOfUpdate: int
    paymentStatus: int
    viewStatus: Optional[int]
    buyerViewStatus: Any
    downloadStatus: Any
    buyerDownloadStatus: Any
    exchangeStatus: Any
    invoiceTemplateId: int
    numOfExchange: int
    contractId: Any
    originalInvoiceNo: Any
    buyerEmailAddress: Optional[str]
    paymentMethod: Any
    feeType: Any
    buyerUnitName: Any
    buyerLegalName: Optional[str]
    paymentTime: Any
    exchangeTime: Any
    exchangeUser: Any
    cusGetInvoiceRight: int
    paymentType: str
    paymentTypeName: str
    originalIssueDate: Any
    invoiceNote: Any
    paymentMethodName: str
    customerId: Any
    domain: str
    serviceType: Any
    serviceTypeName: Any
    noCheckPaymentStatus: Any
    parentSupplierTaxCode: Any
    tenantId: int
    autoCreatePdfInstance: int
    tenantTaxCode: Any
    invoiceTypeId: Any
    buyerPhoneNumber: Any
    additionalReferenceDesc: Optional[str]
    additionalReferenceDate: Optional[str]
    invoiceData: str
    adjustedStatus: Optional[int]
    numOfAdjusted: Optional[int]
    taxDeclarationStatus: Any
    transactionUuid: Any
    authenUsername: str
    buyerCode: Optional[str]
    agreementFilePath: Any
    agreementFileName: Any
    specificationFilePath: Any
    supplierId: Any
    keepInvoiceNo: Optional[bool] = None
    folderExchange: Any
    autoSendGDTStatus: Any
    autoSendGDTError: Any
    buyerSigned: bool
    adjustAmount20: int
    specificationFileName: Any


class InvoiceDataControlResponse(BaseModel):
    errorCode: str
    description: str
    lstInvoiceBO: List[Invoice_SearchInvoice]
