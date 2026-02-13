from __future__ import annotations
from datetime import date
from typing import Any, List, Optional
from pydantic import BaseModel as _BaseModel, Field
from ..base_model import BaseModel

class TTinItem(BaseModel):
    DLieu: Optional[str]
    KDLieu: str
    TTruong: str


class TTHDLQuan(BaseModel):
    TCHDon: int
    LHDCLQuan: int
    KHMSHDCLQuan: str
    KHHDCLQuan: str
    SHDCLQuan: int
    NLHDCLQuan: str
    GChu: Optional[str] = None


class TTKhac(BaseModel):
    TTin: List[TTinItem]


class TTChung(BaseModel):
    PBan: str
    THDon: str
    KHMSHDon: str
    KHHDon: str
    SHDon: str
    NLap: date
    DVTTe: str
    TGia: str
    HTTToan: str
    MSTTCGP: str
    MSTDVNUNLHDon: Any
    TDVNUNLHDon: Any
    DCDVNUNLHDon: Any
    TTHDLQuan: Optional[TTHDLQuan] = None
    TTKhac: TTKhac


class NBan(BaseModel):
    Ten: Optional[str] = None
    MST: Optional[str] = None
    DChi: Optional[str] = None
    SDThoai: Optional[Any] = None
    DCTDTu: Optional[str] = None
    STKNHang: Optional[Any] = None
    TNHang: Optional[Any] = None
    Fax: Optional[Any] = None
    Website: Optional[Any] = None
    TTKhac: Optional[TTKhac] = None


class NMua(BaseModel):
    Ten: Optional[str] = None
    MST: Optional[str] = None
    DChi: Optional[str] = None
    MKHang: Optional[str] = None
    SDThoai: Optional[Any] = None
    DCTDTu: Optional[str] = None
    HVTNMHang: Optional[Any] = None
    STKNHang: Optional[Any] = None
    TNHang: Optional[Any] = None
    TTKhac: Optional[TTKhac] = None


class HHDVu(BaseModel):
    TChat: Optional[str] = None
    STT: Optional[str] = None
    MHHDVu: Optional[str] = None
    THHDVu: Optional[str] = None
    DVTinh: Optional[str] = None
    SLuong: Optional[str] = None
    DGia: Optional[str] = None
    TLCKhau: Optional[Any] = None
    STCKhau: Optional[str] = None
    ThTien: Optional[str] = None
    TSuat: Optional[str] = None
    TTKhac: Optional[TTKhac] = None


class DSHHDVu(BaseModel):
    HHDVu: List[HHDVu]


class LTSuat(BaseModel):
    TSuat: str
    TThue: str
    ThTien: str


class THTTLTSuat(BaseModel):
    LTSuat: LTSuat


class TToan(BaseModel):
    THTTLTSuat: THTTLTSuat
    TgTCThue: str
    TgTThue: str
    DSLPhi: Any
    TTCKTMai: str
    TgTTTBSo: str
    TgTTTBChu: str
    TTKhac: Optional[TTKhac] = None


class NDHDon(BaseModel):
    NBan: NBan
    NMua: NMua
    DSHHDVu: DSHHDVu
    TToan: TToan


class DLHDon(BaseModel):
    _Id: str = Field(..., alias="@Id")
    TTChung: TTChung
    NDHDon: NDHDon


class MCCQT(BaseModel):
    _Id: str = Field(..., alias="@Id")
    text: str = Field(..., alias="#text")


class CanonicalizationMethod(BaseModel):
    _Algorithm: str = Field(..., alias="@Algorithm")


class SignatureMethod(BaseModel):
    _Algorithm: str = Field(..., alias="@Algorithm")


class Transform(BaseModel):
    _Algorithm: str = Field(..., alias="@Algorithm")


class Transforms(BaseModel):
    Transform: Transform


class DigestMethod(BaseModel):
    _Algorithm: str = Field(..., alias="@Algorithm")


class ReferenceItem(BaseModel):
    _URI: str = Field(..., alias="@URI")
    Transforms: Optional[Transforms] = None
    DigestMethod: DigestMethod
    DigestValue: str
    _Type: Optional[str] = Field(None, alias="@Type")


class SignedInfo(BaseModel):
    CanonicalizationMethod: CanonicalizationMethod
    SignatureMethod: SignatureMethod
    Reference: List[ReferenceItem]


class X509Data(BaseModel):
    X509SubjectName: str
    X509Certificate: str


class KeyInfo(BaseModel):
    X509Data: X509Data


class SignatureProperty(BaseModel):
    _Id: str = Field(..., alias="@Id")
    _Target: str = Field(..., alias="@Target")
    SigningTime: str


class SignatureProperties(BaseModel):
    _Id: str = Field(..., alias="@Id")
    SignatureProperty: SignatureProperty


class Object(BaseModel):
    _Id: str = Field(..., alias="@Id")
    SignatureProperties: SignatureProperties


class Signature(BaseModel):
    _xmlns: str = Field(..., alias="@xmlns")
    _Id: str = Field(..., alias="@Id")
    SignedInfo: SignedInfo
    SignatureValue: Optional[Any] = None
    KeyInfo: KeyInfo
    Object: Object


class NBanSignature(BaseModel):
    Signature: Signature


class CQT(BaseModel):
    Signature: Signature


class DSCKS(BaseModel):
    NBan: NBanSignature
    CQT: Optional[CQT] = None


class HDon(BaseModel):
    DLHDon: DLHDon
    MCCQT: Optional[MCCQT] = None
    DSCKS: DSCKS


class VatInvoiceModel(BaseModel):
    HDon: HDon
