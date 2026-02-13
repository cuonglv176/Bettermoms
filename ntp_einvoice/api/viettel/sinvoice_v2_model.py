from datetime import datetime
from enum import Enum
from typing import Any, List, Literal, Optional
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
    total: float
    issueDate: Optional[Any] = None
    issueDateStr: Optional[datetime] = None
    state: int
    requestDate: Optional[Any] = None
    description: Optional[Any] = None
    buyerIdNo: Optional[Any] = None
    stateCode: int
    subscriberNumber: Optional[Any] = None
    paymentStatus: Optional[int] = None
    viewStatus: Optional[Any] = None
    downloadStatus: Optional[Any] = None
    exchangeStatus: int
    numOfExchange: Optional[Any] = None
    createTime: Optional[Any] = None
    contractId: Optional[Any] = None
    contractNo: Optional[Any] = None
    supplierTaxCode: str
    buyerTaxCode: Optional[Any] = None
    totalBeforeTax: float
    taxAmount: float
    taxRate: Optional[Any] = None
    paymentMethod: str
    paymentTime: Optional[Any] = None
    customerId: Optional[Any] = None
    no: Optional[Any] = None
    paymentStatusName: str
    buyerName: Optional[str] = None


class GetInvoicesResponse(BaseModel):
    errorCode: Literal[None]
    description: Optional[str] = None
    totalRows: int
    invoices: List[Invoice_GetInvoice]


# api_get_invoice_attachment
class GetInvoiceAttachmentResponse(BaseModel):
    errorCode: Optional[Literal[200]] = None
    description: Optional[str] = None
    fileToBytes: str
    paymentStatus: bool
    fileName: str


#


class ActionInvoiceDTO(BaseModel):
    adjustInfo: int
    adjustMoney: int
    replace: int
    delete: int
    exchange: int
    sendEmail: int
    sendSMS: int
    pay: int
    downloadExchange: int
    restore: int


class Invoice_SearchInvoice(BaseModel):
    id: int
    state: int
    createdBy: str
    createdDate: str
    lastModifiedBy: Optional[str] = None
    lastModifiedDate: Optional[datetime] = None
    transactionUuid: Optional[Any] = None
    authenUsername: Optional[Any] = None
    supplierId: Optional[Any] = None
    cancelFileName: Optional[Any] = None
    invoiceType: Optional[str] = None
    adjustmentType: str
    supplierTaxCode: Optional[Any] = None
    templateCode: str
    username: Optional[Any] = None
    password: Optional[Any] = None
    backOffice: Optional[Any] = None
    issueDate: datetime
    invoiceSeri: str
    invoiceNumber: Optional[int] = None
    invoiceNo: str
    buyerIdType: Optional[Any] = None
    buyerIdTypeName: Optional[Any] = None
    buyerIdNo: Optional[Any] = None
    buyerTaxCode: Optional[Any] = None
    buyerName: Optional[str] = None
    buyerAddress: Optional[str] = None
    bankName: Optional[Any] = None
    bankAccount: Optional[Any] = None
    deliveryOrder: Optional[Any] = None
    deliveryWarehouse: Optional[Any] = None
    warehouse: Optional[Any] = None
    deliveryCarrier: Optional[Any] = None
    deliveryVehicle: Optional[Any] = None
    contractNo: Optional[Any] = None
    totalAmountWithoutVAT: float
    totalVATAmount: float
    discountAmount: float
    totalAmountWithVAT: float
    totalAmountAfterDiscount: float
    totalAmountWithVATFrn: Optional[Any] = None
    totalAmountWithVATInWords: Optional[Any] = None
    invoiceListId: Optional[int] = None
    invoicePath: Optional[Any] = None
    folderId: Optional[Any] = None
    filePath: Optional[Any] = None
    fileName: Optional[Any] = None
    instanceFilePath: Optional[Any] = None
    instanceFileName: Optional[Any] = None
    exchangeFilePath: Optional[Any] = None
    exchangeFileName: Optional[Any] = None
    backofficeRequestTime: Optional[Any] = None
    responseBackofficeTime: Optional[Any] = None
    lastUpdateTime: Optional[Any] = None
    tempFilePath: Optional[Any] = None
    tempFileName: Optional[Any] = None
    errorCode: str
    description: Optional[Any] = None
    currencyCode: str
    reservationCode: str
    signatureValue: Optional[str] = None
    digestValue: Optional[Any] = None
    createTime: Optional[Any] = None
    stateCode: Optional[Any] = None
    status: Optional[Any] = None
    numOfUpdate: Optional[int] = None
    paymentStatus: int
    viewStatus: Optional[Any] = None
    buyerViewStatus: int
    downloadStatus: Optional[Any] = None
    buyerDownloadStatus: Optional[Any] = None
    exchangeStatus: int
    invoiceTemplateId: int
    numOfExchange: Optional[Any] = None
    contractId: Optional[Any] = None
    originalInvoiceNo: Optional[Any] = None
    buyerEmailAddress: Optional[Any] = None
    paymentMethod: str
    feeType: Optional[Any] = None
    buyerUnitName: Optional[Any] = None
    paymentTime: Optional[Any] = None
    exchangeTime: Optional[Any] = None
    cusGetInvoiceRight: Optional[int] = None
    paymentType: Optional[Any] = None
    paymentTypeName: Optional[Any] = None
    originalIssueDate: Optional[Any] = None
    invoiceNote: Optional[Any] = None
    exchangeUser: Optional[Any] = None
    paymentMethodName: str
    customerId: Optional[Any] = None
    domain: Optional[Any] = None
    serviceType: Optional[Any] = None
    serviceTypeName: Optional[Any] = None
    noCheckPaymentStatus: Optional[Any] = None
    parentSupplierTaxCode: Optional[Any] = None
    tenantId: Optional[Any] = None
    autoCreatePdfInstance: Optional[int] = None
    tenantTaxCode: str
    createUser: Optional[Any] = None
    buyerPhoneNumber: Optional[Any] = None
    invoiceTypeId: int
    additionalReferenceDesc: Optional[Any] = None
    additionalReferenceDate: Optional[Any] = None
    buyerLegalName: Optional[Any] = None
    adjustmentInvoiceType: Optional[Any] = None
    adjustedStatus: int
    numOfAdjusted: Optional[Any] = None
    taxDeclarationStatus: Optional[int] = None
    invoiceRequestId: Optional[Any] = None
    transactionId: Optional[str] = None
    buyerCode: Optional[str] = None
    buyerSigned: Optional[int] = None
    agreementFilePath: Optional[Any] = None
    agreementFileName: Optional[Any] = None
    specificationFilePath: Optional[Any] = None
    specificationFileName: Optional[Any] = None
    keepInvoiceNo: Optional[Any] = None
    invoiceStatus: int
    invoiceTemplateFile: Optional[Any] = None
    invoiceFileXml: Optional[Any] = None
    processStatus: int
    listProduct: Optional[Any] = None
    listInfoUpdate: Optional[Any] = None
    invoiceTemplateName: Optional[Any] = None
    productLst: Optional[Any] = None
    exchangeRate: Optional[float] = None
    listElectricityWater: Optional[Any] = None
    reasonRecovery: Optional[Any] = None
    indexStr: Optional[Any] = None
    hospitalDataDTO: Optional[Any] = None
    lstProduct: Optional[Any] = None
    taxPolicy: Optional[Any] = None
    discountPolicy: Optional[Any] = None
    issueDateStr: Optional[Any] = None
    customerCode: Optional[Any] = None
    parentTenantTaxCode: Optional[Any] = None
    typeSigined: Optional[Any] = None
    hashCode: Optional[Any] = None
    tenantBranchId: int
    signatureType: Optional[Any] = None
    actionInvoiceDTO: ActionInvoiceDTO
    isAction: int
    certString: Optional[Any] = None
    serial: Optional[Any] = None
    hashValue: Optional[Any] = None
    isFile: int
    sellerInfo: Optional[Any] = None
    hasSeller: Optional[Any] = None
    errorDescription: Optional[Any] = None
    reasonDelete: Optional[Any] = None


class Sort(BaseModel):
    unsorted: bool
    sorted: bool
    empty: bool


class Pageable(BaseModel):
    sort: Sort
    pageNumber: int
    pageSize: int
    offset: int
    unpaged: bool
    paged: bool


class Sort1(BaseModel):
    unsorted: bool
    sorted: bool
    empty: bool


class SearchInvoice_Data(BaseModel):
    content: List[Invoice_SearchInvoice]
    pageable: Pageable
    totalPages: int
    totalElements: int
    last: bool
    sort: Sort1
    numberOfElements: int
    first: bool
    size: int
    number: int
    empty: bool


class SearchInvoice(BaseModel):
    code: int
    message: str
    data: SearchInvoice_Data


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
    itemCode: Optional[str] = None
    itemName: Optional[str] = None
    unitCode: Optional[str] = None
    unitName: Optional[str] = None
    unitPrice: Optional[float] = None
    quantity: Optional[float] = None
    itemTotalAmountWithoutTax: Optional[float] = None
    taxPercentage: Optional[float] = None
    taxAmount: Optional[float] = None
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
