# -*- coding: utf-8 -*-
import time
import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin
import requests
import json
import re
from requests.auth import HTTPBasicAuth
from num2words import num2words
from bs4 import BeautifulSoup
from io import BytesIO
from zipfile import ZipFile
import base64, os

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ":HIGH:!DH:!aNULL"
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += (
        ":HIGH:!DH:!aNULL"
    )
except AttributeError:
    # no pyopenssl support used / needed / available
    pass

_logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from ..models.company_branch import CompanyBranch


"""
SInvoiceAPI Feature List

1. authentication
- auto refresh token base on request

2. create invoice
3. adjust invoice
4. cancel invoice
5. restore canceled invoice

"""

class SInvoiceApi:
    def __init__(self, branch: "CompanyBranch"):
        self.branch = branch
        self.base_headers = {"Content-Type": "application/json"}
        self.base_url = branch.vsi_domain
        self.auth_url = urljoin(self.base_url, "auth/login")
        self.access_token, self.refresh_token, self.expires_in = None, None, None
        self.last_call_time = datetime.now()
        self.update_token()
        self.version = self.branch.vsi_version

    def is_expired(self):
        if self.expires_in == None:
            return True
        if (datetime.now() - self.last_call_time).seconds >= self.expires_in:
            return True
        return False

    def get_header(self, **kwargs):
        headers = self.base_headers.copy()
        headers.update(**kwargs)
        return headers

    def get_auth_cred(self):
        return {
            "username": self.branch.vsi_username,
            "password": self.branch.vsi_password,
        }

    def update_token(self):
        if self.is_expired():
            (
                self.access_token,
                self.refresh_token,
                self.expires_in,
            ) = self._get_access_token()

    def _get_access_token(self):
        data = requests.post(
            self.auth_url, headers=self.get_header(), json=self.get_auth_cred()
        )
        try:
            data = data.json()
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            expires_in = data["expires_in"]
            return access_token, refresh_token, expires_in
        except Exception as e:
            return None, None, None

    def _request(self, url, data):
        if self.version == "v2":
            self.update_token()
            return requests.post(
                url,
                headers=self.get_header(Cookie=f"access_token={self.access_token}"),
                json=data,
            )
        else:
            return requests.post(
                url,
                headers=self.get_header(),
                auth=HTTPBasicAuth(self.branch.vsi_username, self.branch.vsi_password),
                json=data,
            )

    def act_get_invoices(self):
        row_per_page = 50
        start_date = self.branch.vsi_invoice_pull_start_date.strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        data = {
            "startDate": start_date,
            "endDate": end_date,
            "rowPerPage": row_per_page,
            "pageNum": 1,
            "invoiceSeri": self.branch.vsi_series,  # only this serie
        }
        if self.version == "v2":
            url = urljoin(
                self.base_url,
                f"services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/getInvoices/{self.branch.vsi_tin}",
            )
            res = self._request(url, data)
            if res.json()["errorCode"]:
                raise UserError(f"Cannot get invoice via api - {res.text}")

            res_json = res.json()
            total_invoice = res_json["totalRows"]
            total_page = int(total_invoice / row_per_page) + (
                1 if total_invoice % row_per_page != 0 else 0
            )
            invoices = res_json["invoices"]
            if total_page == 1:
                pass
            else:
                for page in range(2, total_page + 1):
                    data["pageNum"] = page
                    res = res = self._request(url, data)
                    invoices += res.json()["invoices"]
        else:
            raise ValueError("not support v1 yet")

        return invoices

    def act_get_invoice_attachment(
        self, supplier_tax_code, template_code, invoice_no, type="pdf"
    ):
        data = {
            "supplierTaxCode": supplier_tax_code,
            "templateCode": template_code,
            "invoiceNo": invoice_no,
            "fileType": type,
        }

        if self.version == "v2":
            url = urljoin(
                self.base_url,
                f"services/einvoiceapplication/api/InvoiceAPI/InvoiceUtilsWS/getInvoiceRepresentationFile",
            )
            res = self._request(url, data)
        else:
            url = urljoin(
                self.base_url, f"InvoiceAPI/InvoiceUtilsWS/getInvoiceRepresentationFile"
            )
            res = self._request(url, data)
        if not res.json()["errorCode"] or res.json()["errorCode"] == 200:
            return res.json()
        return None

    def act_get_invoice_status_detail(self, invoice_no):
        if self.branch.vsi_version == "v1":
            return {}
        url = urljoin(self.base_url, f"services/einvoiceapplication/api/invoice/search")
        params = {"invoiceNo.equals": invoice_no, "invoiceStatus.equals": 1}
        rsp = requests.get(
            url,
            params=params,
            headers=self.get_header(Cookie=f"access_token={self.access_token}"),
        )
        try:
            data = rsp.json()
            return {
                "invoiceNo": data["data"]["content"][0]["invoiceNo"],
                "adjustmentType": data["data"]["content"][0]["adjustmentType"],
                "id": data["data"]["content"][0]["id"],
                "errorCode": data["data"]["content"][0]["errorCode"],
                "errorDescription": data["data"]["content"][0]["errorDescription"],
                "reasonDelete": data["data"]["content"][0]["reasonDelete"],
                "additionalReferenceDesc": data["data"]["content"][0][
                    "additionalReferenceDesc"
                ],
                "additionalReferenceDate": data["data"]["content"][0][
                    "additionalReferenceDate"
                ],
                "reservationCode": data["data"]["content"][0]["reservationCode"],
            }
        except Exception as e:
            return {}

    def act_create_einvoice(self, data):
        url = urljoin(self.base_url, f"services/einvoiceapplication/api/InvoiceAPI/InvoiceWS/createInvoice/{self.branch.vsi_tin}")
        res = self._request(url, data)
        return res

    def act_create_exchange_invoice_file(self):
        pass

    def act_cancel_invoice(self, invoice_no, additional_desc, additional_date: "datetime"):
        invoice_detail = self.act_get_invoice_status_detail(invoice_no)
        invoice_id = invoice_detail['id']
        url = urljoin(self.base_url, f'services/einvoiceapplication/api/invoice/delete-invoice-released')
        data = {
            "additionalReferenceDate": additional_date.strftime("%Y-%m-%dT%H:%M:%SZ"), # "2022-03-22T17:00:00.000Z",
            "additionalReferenceDesc": additional_desc,
            "agreementFileName": None,
            "agreementFilePath": None,
            "docDeal": None,
            "id": invoice_id,
            "reason": additional_desc,
        }
        res = requests.put(url, json=data, headers=self.get_header(Cookie=f"access_token={self.access_token}"))
        return res

        # return
        # url = urljoin(self.base_url, f"services/einvoiceapplication/api/InvoiceAPI/InvoiceWS/cancelTransactionInvoice")
        # params = {
        #     "supplierTaxCode": supplier_tax_code,
        #     # "templateCode": template_code,
        #     "invoiceNo": invoice_no,
        #     "strIssueDate": issue_date.strftime("%s"),
        #     "additionalReferenceDesc": additional_desc,
        #     "additionalReferenceDate": issue_date.strftime("%Y%m%d%H%M%S")
        # }
        # headers = {
        #     "Content-Type": "application/x-www-form-urlencoded",
        #     "Cookie": f"access_token={self.access_token}"
        # }
        # res = requests.post(url, data=params, headers=self.get_header(**headers))
        # print(res)
        # return res
