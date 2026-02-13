from typing import Union
import xmltodict
from ..api.schema.vat_invoice_model import VatInvoiceModel


class VatEInvoiceReader:
    def __init__(self, xml_data: Union[str, bytes]):
        self.xml_data = xml_data
        self.xml_data_dict = xmltodict.parse(xml_data)
        try:
            self.xml_data_model = VatInvoiceModel(**self.xml_data_dict)
        except:
            if issubclass(type(self.xml_data_dict['HDon']['DLHDon']['NDHDon']['DSHHDVu']['HHDVu']), dict):
                item = self.xml_data_dict['HDon']['DLHDon']['NDHDon']['DSHHDVu']['HHDVu']
                self.xml_data_dict['HDon']['DLHDon']['NDHDon']['DSHHDVu']['HHDVu'] = [item]
                self.xml_data_model = VatInvoiceModel(**self.xml_data_dict)
            else:
                raise

    def get_seller_info(self):
        seller_info = self.xml_data_model.HDon.DLHDon.NDHDon.NBan
        return {
            "seller_name": seller_info.Ten,
            "seller_tax_code": seller_info.MST,
            "seller_address": seller_info.DChi,
            "seller_phone_number": seller_info.SDThoai,
            "seller_email": seller_info.DCTDTu,
            "seller_code": None,
            "seller_bank_name": seller_info.TNHang,
            "seller_bank_account": seller_info.STKNHang,
            "seller_website": seller_info.Website,
        }

    def get_buyer_info(self):
        buyer_info = self.xml_data_model.HDon.DLHDon.NDHDon.NMua
        return {
            "buyer_name": buyer_info.HVTNMHang,
            "buyer_company_name": buyer_info.Ten,
            "buyer_tax_code": buyer_info.MST,
            "buyer_address": buyer_info.DChi,
            "buyer_phone_number": buyer_info.SDThoai,
            "buyer_email": buyer_info.DCTDTu,
            "buyer_code": buyer_info.MKHang,
            "buyer_bank_name": buyer_info.TNHang,
            "buyer_bank_account": buyer_info.STKNHang,
            "buyer_note": None,
        }

    def get_item_info(self):
        items = []
        for item_data in self.xml_data_model.HDon.DLHDon.NDHDon.DSHHDVu.HHDVu:
            data = {
                "type": item_data.TChat,
                "line_number": item_data.STT,
                "item_code": item_data.MHHDVu,
                "item_name": item_data.THHDVu,
                "item_uom": item_data.DVTinh,
                "item_price_unit": item_data.DGia,
                "item_quantity": item_data.SLuong,
                "item_vat_rate": item_data.TSuat,
                "item_price_subtotal": item_data.ThTien,
                "item_price_total": None,  # default auto calc
                "item_vat_amount": None,  # default auto calc
            }
            # find price_total and vat_amount
            if item_data.TTKhac:
                for other_info in item_data.TTKhac.TTin:
                    if (
                        "Thành tiền thanh toán" in other_info.TTruong
                        and other_info.DLieu
                    ):
                        data["item_price_total"] = other_info.DLieu
                    elif "Tiền thuế" in other_info.TTruong and other_info.DLieu:
                        data["item_vat_amount"] = other_info.DLieu
            items.append(data)
        return items

    def get_general_info(self):
        general_info_data = self.xml_data_model.HDon.DLHDon.TTChung
        general_info = {
            "currency": general_info_data.DVTTe,
            "payment_method": general_info_data.HTTToan,
            "invoice_template_type": general_info_data.KHMSHDon,
            "invoice_series": general_info_data.KHHDon,
            "invoice_id": general_info_data.SHDon,
            "issue_date": general_info_data.NLap,
            "payment_status": "unpaid",
        }
        # other info
        for other_info in general_info_data.TTKhac.TTin:
            if other_info.TTruong == "Trạng thái thanh toán":
                if "đã" in other_info.DLieu.lower():
                    general_info["payment_status"] = "paid"
        # payment
        payment_info = self.xml_data_model.HDon.DLHDon.NDHDon.TToan
        # TODO: need to handle cases that have multiple vat applied
        # ! may be problem will come from here
        general_info['vat_rate'] = payment_info.THTTLTSuat.LTSuat.TSuat
        general_info['total_amount_without_vat'] = payment_info.TgTCThue
        general_info['total_vat_amount'] = payment_info.TgTThue
        general_info['total_amount_with_vat'] = payment_info.TgTTTBSo
        general_info['discount_amount'] = payment_info.TTCKTMai
        general_info['total_amount_with_vat_in_words'] = payment_info.TgTTTBChu
        return general_info

    def get_related_invoice(self):
        related_invoice = self.xml_data_model.HDon.DLHDon.TTChung.TTHDLQuan
        if not related_invoice:
            return {}
        return {
            'invoice_properties': related_invoice.TCHDon,
            'invoice_type': related_invoice.LHDCLQuan,
            'invoice_template_type': related_invoice.KHMSHDCLQuan,
            'invoice_series': related_invoice.KHHDCLQuan,
            'invoice_no': related_invoice.SHDCLQuan,
            'invoice_issue_date': related_invoice.NLHDCLQuan,
            'note': related_invoice.GChu
        }

    def get_dynamic_provider_data(self):
        """
        return some information like CQT: Tax Departement Approved Code

        Name              Value
        -----------------------
        Ghi chú           ...
        Mã số bí mật      ...
        """
        dynamic_data = []
        # in general info
        general_info_data = self.xml_data_model.HDon.DLHDon.TTChung
        tax_department_approval = self.xml_data_model.HDon.MCCQT
        signatures = self.xml_data_model.HDon.DSCKS
        for other_info in general_info_data.TTKhac.TTin:
            dynamic_data.append([other_info.TTruong, other_info.DLieu])
        if tax_department_approval:
            dynamic_data.append(['MCCQT (Tax Authorities Approved Code)', tax_department_approval.text])
        # signature
        if signatures:
            if signatures.NBan:
                dynamic_data.append(["Signed By Seller", "Yes"])
            else:
                dynamic_data.append(["Signed By Seller", "No"])
            if signatures.CQT:
                dynamic_data.append(["Signed By Tax Authorities", "Yes"])
            else:
                dynamic_data.append(["Signed By Tax Authorities", "No"])
        return dynamic_data

    def get_mccqt(self):
        tax_department_approval = self.xml_data_model.HDon.MCCQT
        if tax_department_approval:
            return tax_department_approval.text
        return False
