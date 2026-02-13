import tempfile
from typing import Literal, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pdfkit
import os
import re


MST_BASEURL = "http://tracuunnt.gdt.gov.vn"
MST_COMPANY = urljoin(MST_BASEURL, "tcnnt/mstdn.jsp")
MST_INDIVIDUAL = urljoin(MST_BASEURL, "tcnnt/mstcn.jsp")

request_pool = {}


def get_session(uid, reset=False):
    if uid not in request_pool or reset:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "A Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.82 Safari/537.36",
            }
        )
        request_pool[uid] = session
    return request_pool[uid]


class MstFinder:
    def __init__(
        self, session: requests.Session, finder=Literal["individual", "company"]
    ):
        self.session = session
        self.base_url = MST_BASEURL
        if finder == "individual":
            self.url = MST_INDIVIDUAL
        else:
            self.url = MST_COMPANY
        self.finder = finder

    def get_captcha(self):
        res = self.session.get(self.url)

        # ! 20221205: http://tracuunnt.gdt.gov.vn/tcnnt/mstdn.jsp change the way to set cookie
        # so need to validate res.text has captcha img or it is set cookie
        # <html><body><script>document.cookie="D1N=7e6fe5afe5587141221ddd7a32c45657"+"; path=/";window.location.reload(true);</script></body></html>
        js_cookie = re.findall(".+D1N=([a-z0-9]{32}).+", res.text)
        if js_cookie:
            self.session.cookies.update({"D1N": js_cookie[0]})
            res = self.session.get(MST_COMPANY)

        bs = BeautifulSoup(res.text, features="lxml")
        # NOTE: this is required to make session work
        captcha = bs.find("img")["src"]
        captcha_url = urljoin(self.base_url, captcha)
        captcha_img = self.session.get(captcha_url)
        return captcha_url, captcha_img.content

    def get_mst_detail(self, mst, captcha):
        if self.finder == "company":
            data = {
                "action": "action",
                "id": "",
                "page": "1",
                "mst": mst,
                "fullname": "",
                "address": "",
                "cmt": "",
                "captcha": captcha,
            }
            res_mst = self.session.post(self.url, data=data)

            data_detail = {
                "action": "action",
                "id": mst,
                "page": "1",
                "mst": mst,
                "fullname": "",
                "address": "",
                "cmt": "",
                "captcha": "",
            }
            res_mst_detail = self.session.post(self.url, data=data_detail)
            bs_mst_detail = BeautifulSoup(res_mst_detail.content, features="lxml")

            map_data = {
                "Mã số doanh nghiệp": "tax_code",
                "Ngày cấp": "issue_date",
                "Ngày đóng MST": "tax_issue_date",
                "Tên chính thức": "legal_name",
                "Tên giao dịch": "trade_name",
                "Nơi đăng ký quản lý thuế": "tax_administration_registration_place",
                "Địa chỉ trụ sở": "office_address",
                "Nơi đăng ký nộp thuế": "tax_registration_place",
                "Địa chỉ nhận thông báo thuế": "address_to_receive_tax_notice",
                "QĐTL-Ngày cấp": "date_of_issuance_of_the_decision_on_establishment",
                "Cơ quan ra quyết định": "issuance_from",
                "GPKD-Ngày cấp": "date_of_issuance_of_the_business_license",
                "Cơ quan cấp": "business_license_issued_by",
                "Ngày nhận tờ khai": "registration_date_of_business_license",
                "Ngày/tháng bắt đầu năm tài chính": "financial_start_date",
                "Ngày/tháng kết thúc năm tài chính": "financial_stop_date",
                "Mã số hiện thời": "code",
                "Ngày bắt đầu HĐ": "start_date_of_operation",
                "Hình thức h.toán": "accounting_method",
                "PP tính thuế GTGT": "vat_calculation_method",
                "Chủ sở hữu/Người đại diện pháp luật": "owner_legal_representative",
                "Địa chỉ chủ sở hữu/người đại diện pháp luật": "address_of_owner_legal_representative",
                "Tên giám đốc": "director",
                # "Địa Chỉ": "address_of_director",
                "Kế toán trưởng": "chief_accountant",
                # "Địa Chỉ": "address_of_chief_accountant",
            }

            company_data = []
            try:
                table_data = bs_mst_detail.find_all("table", {"class": "ta_border"})[0]
                cursor = None
                for row in table_data.select("tr"):
                    for tag in row.select("th,td"):
                        striped_text = tag.text.strip()
                        if striped_text in map_data:
                            cursor = striped_text
                            continue
                        if cursor and tag.name == "td":
                            value = striped_text
                            if cursor == "GPKD-Ngày cấp":
                                value = value.replace("\xa0", " ")
                            company_data.append([cursor, map_data[cursor], value])
                            cursor = None
            except Exception as err:
                raise

            # replace css link / img link be visivble
            html = res_mst_detail.text.replace('href="css/', f'href="{MST_BASEURL}/tcnnt/css/')
            html = html.replace('src="/tcnnt/', f'src="{MST_BASEURL}/tcnnt/')
            options = {'encoding': "UTF-8"}
            pdf_path = os.path.join(tempfile.mkdtemp(), 'result.pdf')
            try:
                pdfkit.from_string(html, output_path=pdf_path, options=options)
            except:
                # for odoo.sh
                config = pdfkit.configuration(wkhtmltopdf="/usr/local/bin/wkhtmltopdf.bin")
                pdfkit.from_string(html, output_path=pdf_path, options=options, configuration=config)
            with open(pdf_path, 'rb') as f:
                pdf = f.read()
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return company_data, html, pdf


def get_finder(uid, finder=Literal["individual", "company"], reset: Optional[bool] = False):
    return MstFinder(get_session(uid, reset=reset), finder=finder)


if __name__ == "__main__":
    finder = get_finder(1, "company")
    print(finder.get_captcha()[0])
    captcha = input("Your Captcha: ").strip()
    mst = "0108951191"
    data = finder.get_mst_detail(mst, captcha)
    breakpoint()
