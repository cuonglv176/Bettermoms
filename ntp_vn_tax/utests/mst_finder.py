import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from lxml import etree
import re

MST_BASEURL = "http://tracuunnt.gdt.gov.vn"
MST_COMPANY = urljoin(MST_BASEURL, "tcnnt/mstdn.jsp")
MST_INDIVIDUAL = urljoin(MST_BASEURL, "tcnnt/mstcn.jsp")

mst = "0108951191"

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.82 Safari/537.36",
    }
)

res = session.get(MST_COMPANY)

# validate res.text has captcha img
js_cookie = re.findall(".+D1N=([a-z0-9]{32}).+", res.text)
if js_cookie:
    session.cookies.update({"D1N": js_cookie[0]})
    res = session.get(MST_COMPANY)

bs = BeautifulSoup(res.text, features="lxml")
captcha = bs.find("img")["src"]


captcha_img = session.get(urljoin(MST_BASEURL, captcha))

print(urljoin(MST_BASEURL, captcha))

captcha_code = input("Your Captcha: ").strip()
data = {
    "action": "action",
    "id": "",
    "page": "1",
    "mst": mst,
    "fullname": "",
    "address": "",
    "cmt": "",
    "captcha": captcha_code,
}

res_mst = session.post(MST_COMPANY, data=data)

data = {
    "action": "action",
    "id": mst,
    "page": "1",
    "mst": mst,
    "fullname": "",
    "address": "",
    "cmt": "",
    "captcha": "",
}

res_mst_detail = session.post(MST_COMPANY, data=data)

bs_mst_detail = BeautifulSoup(res_mst_detail.content)


map_data = {
    "Mã số doanh nghiệp	": "tax_code",
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
    "GPKD-Ngày cấp": "financial_year_start_at",
    "Cơ quan cấp": "financial_year_stop_at",
    "Ngày nhận tờ khai": "current_code",
    "Ngày/tháng bắt đầu năm tài chính": "contract_start_date",
    "Ngày/tháng kết thúc năm tài chính": "chaper_clause",
    "Mã số hiện thời": "code",
    "Ngày bắt đầu HĐ": "start_date_of_contract",
    "Hình thức h.toán": "accounting_from",
    "PP tính thuế GTGT": "vat_calculation_method",
    "Chủ sở hữu/Người đại diện pháp luật": "owner_legal_representative",
    "Địa chỉ chủ sở hữu/người đại diện pháp luật": "address_of_owner_legal_representative",
    "Tên giám đốc": "director",
    # "Địa Chỉ": "address_of_director",
    "Kế toán trưởng": "chief_accountant",
    # "Địa Chỉ": "address_of_chief_accountant",
}

try:
    table_data = bs_mst_detail.find_all("table", {"class": "ta_border"})[0]
    company_data = {}
    company_data_en = {}
    cursor = None
    for row in table_data.select("tr"):
        for tag in row.select("th,td"):
            if tag.text in map_data:
                cursor = tag.text
                continue
            if cursor and tag.name == "td":
                value = tag.text.strip()
                if cursor == "GPKD-Ngày cấp":
                    value = value.replace("\xa0", " ")
                company_data[cursor] = value
                company_data_en[map_data[cursor]] = value
                cursor = None
except Exception as e:
    pass

breakpoint()
