# -*- coding: utf-8 -*-
"""
Grab E-Invoice Session Manager
================================
Handles authentication and session management for vn.einvoice.grab.com portal.

The portal (powered by HILO GROUP) uses:
  - ASP.NET MVC with CSRF token (__RequestVerificationToken)
  - Image-based CAPTCHA (CaptchaHash cookie stores MD5 of the expected answer)
  - Cookie-based session (.ASPXAUTH)

Login Flow:
  1. GET  /tai-khoan/dang-nhap  -> receive CSRF token + session cookie
  2. GET  /Captcha/Show         -> receive CAPTCHA image (PNG 500x100) + CaptchaHash cookie
  3. POST /tai-khoan/dang-nhap  -> submit UserName, Password, captch, __RequestVerificationToken
  4. On success: redirect to /hoa-don/danh-sach with .ASPXAUTH cookie

Invoice Fetch Flow (after login):
  - GET /hoa-don/danh-sach      -> HTML page with invoice table
  - POST /Invoice/DowloadData   -> Download PDF/XML as ZIP
"""

import base64
import logging
import re
import time
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)

GRAB_PORTAL_BASE = "https://vn.einvoice.grab.com"
LOGIN_PATH = "/tai-khoan/dang-nhap"
CAPTCHA_PATH = "/Captcha/Show"
INVOICE_LIST_PATH = "/hoa-don/danh-sach"
INVOICE_DOWNLOAD_PATH = "/Invoice/DowloadData"
LOGOUT_PATH = "/Account/SignOut"

# Timeout settings
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 60
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)


def solve_captcha_with_openai(image_bytes, api_key=None):
    """
    Solve a CAPTCHA image using OpenAI Vision API.

    Args:
        image_bytes (bytes): Raw PNG image bytes.
        api_key (str): OpenAI API key. If None, uses OPENAI_API_KEY env var.

    Returns:
        str: CAPTCHA text answer, or empty string on failure.
    """
    try:
        import os
        from openai import OpenAI

        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key

        client = OpenAI(**kwargs)
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")

        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Read the CAPTCHA text from this image. "
                                "Return ONLY the characters/digits you see, "
                                "with no spaces, no explanation. "
                                "The captcha has 4-6 alphanumeric characters "
                                "on a green background."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,%s" % img_b64,
                            },
                        },
                    ],
                }
            ],
            max_tokens=20,
        )
        answer = response.choices[0].message.content.strip()
        # Remove any spaces or special characters
        answer = re.sub(r"[^A-Za-z0-9]", "", answer)
        _logger.info("CAPTCHA auto-solved: '%s'", answer)
        return answer

    except Exception as e:
        _logger.error("Failed to solve CAPTCHA with OpenAI: %s", e)
        return ""


class GrabEInvoiceSession:
    """
    Manages an authenticated session with the Grab e-invoice portal.

    Usage (manual CAPTCHA)::

        session = GrabEInvoiceSession(username, password)
        session.prepare_login()
        captcha_bytes = session.get_captcha_image()
        # Show captcha to user, get answer
        success = session.login(captcha_answer)

    Usage (auto CAPTCHA via OpenAI)::

        session = GrabEInvoiceSession(username, password)
        success = session.auto_login(openai_api_key="sk-...")
        if success:
            result = session.fetch_invoices("01/02/2026", "23/02/2026")
    """

    def __init__(self, username, password, base_url=None):
        self.username = username
        self.password = password
        self.base_url = (base_url or GRAB_PORTAL_BASE).rstrip("/")
        self._session = self._build_session()
        self._csrf_token = None
        self._authenticated = False
        self._auth_time = None

    def _build_session(self):
        """Build a requests.Session with retry logic and browser-like headers."""
        session = requests.Session()

        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        return session

    def _url(self, path):
        return "%s%s" % (self.base_url, path)

    # ------------------------------------------------------------------
    # Login Flow
    # ------------------------------------------------------------------

    def prepare_login(self):
        """
        Step 1: Load the login page to obtain CSRF token and session cookie.

        Returns:
            bool: True if preparation succeeded.
        """
        _logger.info("Preparing Grab e-invoice login session...")
        response = self._session.get(
            self._url(LOGIN_PATH),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        # Extract CSRF token from hidden input
        # Pattern: <input name="__RequestVerificationToken" type="hidden" value="..."/>
        match = re.search(
            r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',
            response.text,
        )
        if not match:
            match = re.search(
                r'value="([^"]+)"[^>]*name="__RequestVerificationToken"',
                response.text,
            )

        if match:
            self._csrf_token = match.group(1)
            _logger.debug("CSRF token obtained: %s...", self._csrf_token[:30])
        else:
            _logger.warning("Could not extract CSRF token from login page")
            return False

        return True

    def get_captcha_image(self):
        """
        Step 2: Fetch the CAPTCHA image. Must call prepare_login() first.

        Returns:
            bytes: Raw PNG image bytes, or None on failure.
        """
        _logger.info("Fetching CAPTCHA image from Grab portal...")
        response = self._session.get(
            self._url(CAPTCHA_PATH),
            timeout=REQUEST_TIMEOUT,
            headers={
                "Referer": self._url(LOGIN_PATH),
                "Accept": "image/png,image/webp,image/*,*/*;q=0.8",
            },
        )

        content_type = response.headers.get("content-type", "")
        if response.status_code == 200 and (
            content_type.startswith("image/") or len(response.content) > 500
        ):
            _logger.info(
                "CAPTCHA image fetched: %d bytes", len(response.content)
            )
            return response.content

        _logger.warning(
            "Unexpected CAPTCHA response: HTTP %d, Content-Type: %s, size: %d",
            response.status_code, content_type, len(response.content),
        )
        return None

    def get_captcha_image_b64(self):
        """Fetch CAPTCHA image and return as base64 string."""
        raw = self.get_captcha_image()
        if raw:
            return base64.b64encode(raw).decode("utf-8")
        return ""

    def login(self, captcha_answer):
        """
        Step 3: Submit login form with CAPTCHA answer.

        Args:
            captcha_answer (str): The CAPTCHA text.

        Returns:
            bool: True if login was successful.
        """
        if not self._csrf_token:
            raise ValueError(
                "CSRF token not available. Call prepare_login() first."
            )

        _logger.info(
            "Attempting Grab e-invoice login for user: %s (captcha: %s)",
            self.username, captcha_answer,
        )

        payload = {
            "__RequestVerificationToken": self._csrf_token,
            "UserName": self.username,
            "Password": self.password,
            "captch": captcha_answer,  # NOTE: field name is "captch" (not "captcha")
        }

        response = self._session.post(
            self._url(LOGIN_PATH),
            data=payload,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self._url(LOGIN_PATH),
                "Origin": self.base_url,
            },
            allow_redirects=True,
        )

        final_url = response.url
        response_text = response.text

        _logger.info(
            "Login POST result: HTTP %d, final URL: %s",
            response.status_code, final_url,
        )

        # Check for error messages in the response
        error_messages = [
            "Tài khoản hoặc mật khẩu không đúng",
            "Mã kiểm tra không đúng",
            "Mã kiểm tra không hợp lệ",
            "Invalid captcha",
            "Invalid username or password",
        ]
        for err_msg in error_messages:
            if err_msg in response_text:
                _logger.warning("Login failed: %s", err_msg)
                return False

        # Success indicators:
        # 1. Redirected away from login page
        # 2. .ASPXAUTH cookie is set
        aspx_cookie = self._session.cookies.get(".ASPXAUTH")

        if aspx_cookie:
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info(
                "Grab login successful! .ASPXAUTH cookie obtained. Final URL: %s",
                final_url,
            )
            return True

        # Check if redirected away from login page
        if "dang-nhap" not in final_url.lower() and response.status_code == 200:
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info(
                "Grab login appears successful (redirected to: %s)", final_url
            )
            return True

        _logger.warning(
            "Login failed: no .ASPXAUTH cookie and still on login page. "
            "Final URL: %s", final_url,
        )
        return False

    def auto_login(self, openai_api_key=None, max_attempts=3):
        """
        Fully automatic login: prepare, solve CAPTCHA with AI, and login.

        Args:
            openai_api_key (str): OpenAI API key for CAPTCHA solving.
            max_attempts (int): Maximum number of CAPTCHA solve attempts.

        Returns:
            bool: True if login was successful.
        """
        for attempt in range(1, max_attempts + 1):
            _logger.info(
                "Auto-login attempt %d/%d for user: %s",
                attempt, max_attempts, self.username,
            )

            # Step 1: Prepare login page
            if not self.prepare_login():
                _logger.error("Failed to prepare login page (attempt %d)", attempt)
                continue

            # Step 2: Get CAPTCHA image
            captcha_bytes = self.get_captcha_image()
            if not captcha_bytes:
                _logger.error("Failed to get CAPTCHA image (attempt %d)", attempt)
                continue

            # Step 3: Solve CAPTCHA with OpenAI
            captcha_answer = solve_captcha_with_openai(
                captcha_bytes, api_key=openai_api_key
            )
            if not captcha_answer:
                _logger.error("Failed to solve CAPTCHA (attempt %d)", attempt)
                continue

            _logger.info(
                "CAPTCHA solved: '%s' (attempt %d)", captcha_answer, attempt
            )

            # Step 4: Login
            try:
                if self.login(captcha_answer):
                    return True
            except Exception as e:
                _logger.error("Login error (attempt %d): %s", attempt, e)

            # Wait before retry
            if attempt < max_attempts:
                time.sleep(2)

        _logger.error(
            "Auto-login failed after %d attempts for user: %s",
            max_attempts, self.username,
        )
        return False

    def is_authenticated(self):
        """Check if the session is currently authenticated."""
        if not self._authenticated or not self._auth_time:
            return False
        # Sessions typically expire after 30 minutes
        elapsed = datetime.now() - self._auth_time
        if elapsed > timedelta(minutes=25):
            _logger.info("Session may have expired (age: %s)", elapsed)
            self._authenticated = False
            return False
        return True

    def check_session_valid(self):
        """
        Actively check if the session is still valid by making a request.

        Returns:
            bool: True if session is still valid.
        """
        if not self._authenticated:
            return False

        try:
            response = self._session.get(
                self._url(INVOICE_LIST_PATH),
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            # If we get a redirect (302) to login/signout, session is expired
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                if "SignOut" in location or "dang-nhap" in location:
                    _logger.info("Session expired (redirected to: %s)", location)
                    self._authenticated = False
                    return False

            # If we get 200, session is still valid
            if response.status_code == 200:
                # Double check: make sure it's not the login page
                if "Đăng nhập" in response.text and "UserName" in response.text:
                    self._authenticated = False
                    return False
                self._auth_time = datetime.now()  # Refresh timer
                return True

        except Exception as e:
            _logger.warning("Session check failed: %s", e)

        return False

    # ------------------------------------------------------------------
    # Invoice Fetching
    # ------------------------------------------------------------------

    def fetch_invoices(self, date_from=None, date_to=None, page=1, page_size=50):
        """
        Fetch the invoice list from the portal.

        The portal at /hoa-don/danh-sach renders an HTML page with a table.
        We parse the HTML table to extract invoice data.

        Args:
            date_from (str): Start date in 'dd/MM/yyyy' format.
            date_to (str): End date in 'dd/MM/yyyy' format.
            page (int): Page number (1-based).
            page_size (int): Records per page.

        Returns:
            dict: {'invoices': list, 'total': int, 'has_more': bool}
        """
        if not self._authenticated:
            raise ValueError("Not authenticated. Call login() or auto_login() first.")

        if not date_to:
            date_to = datetime.now().strftime("%d/%m/%Y")
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")

        _logger.info(
            "Fetching Grab invoices: %s to %s (page %d, size %d)",
            date_from, date_to, page, page_size,
        )

        # Try to access the invoice list page
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "page": page,
            "pageSize": page_size,
        }

        response = self._session.get(
            self._url(INVOICE_LIST_PATH),
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Referer": self._url(INVOICE_LIST_PATH),
            },
        )

        _logger.info(
            "Invoice list response: HTTP %d, URL: %s, Content-Length: %d",
            response.status_code, response.url, len(response.text),
        )

        # Check if redirected to login (session expired)
        if "dang-nhap" in response.url.lower() or "SignOut" in response.url:
            self._authenticated = False
            raise ValueError(
                "Session expired: redirected to %s" % response.url
            )

        content_type = response.headers.get("content-type", "")

        # Try JSON first (some portals return JSON for AJAX requests)
        if "application/json" in content_type:
            try:
                data = response.json()
                return self._parse_invoice_list_json(data)
            except Exception:
                pass

        # Parse HTML table
        return self._parse_invoice_list_html(response.text, page, page_size)

    def _parse_invoice_list_html(self, html, page, page_size):
        """
        Parse HTML table from the invoice list page.

        The HILO portal typically renders invoices in a <table> with rows like:
        <tr id="invoice_id">
            <td>checkbox</td>
            <td>STT</td>
            <td>Ký hiệu</td>
            <td>Số hóa đơn</td>
            <td>Ngày hóa đơn</td>
            <td>Tên người mua</td>
            <td>MST người mua</td>
            <td>Tổng tiền</td>
            <td>Trạng thái</td>
            ...
        </tr>
        """
        invoices = []

        try:
            # Find the main data table
            # Look for <table> that contains invoice data
            table_match = re.search(
                r'<table[^>]*class="[^"]*table[^"]*"[^>]*>(.*?)</table>',
                html,
                re.DOTALL | re.IGNORECASE,
            )

            if not table_match:
                # Try any table with id
                table_match = re.search(
                    r'<table[^>]*>(.*?)</table>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )

            if not table_match:
                _logger.warning("No table found in invoice list HTML")
                _logger.debug("HTML preview: %s", html[:2000])
                return {"invoices": [], "total": 0, "has_more": False}

            table_html = table_match.group(1)

            # Extract header columns to understand table structure
            header_cells = re.findall(
                r'<th[^>]*>(.*?)</th>',
                table_html,
                re.DOTALL | re.IGNORECASE,
            )
            tag_strip = re.compile(r'<[^>]+>')
            headers = [tag_strip.sub("", h).strip().lower() for h in header_cells]
            _logger.info("Table headers found: %s", headers)

            # Map header positions
            col_map = self._detect_column_map(headers)
            _logger.info("Column mapping: %s", col_map)

            # Parse data rows
            # Match <tr> with or without id attribute
            row_pattern = re.compile(
                r'<tr[^>]*?(?:id="([^"]*)")?[^>]*>(.*?)</tr>',
                re.DOTALL | re.IGNORECASE,
            )
            td_pattern = re.compile(
                r'<td[^>]*>(.*?)</td>',
                re.DOTALL | re.IGNORECASE,
            )

            # Skip header row(s) - find tbody if exists
            tbody_match = re.search(
                r'<tbody[^>]*>(.*?)</tbody>',
                table_html,
                re.DOTALL | re.IGNORECASE,
            )
            search_html = tbody_match.group(1) if tbody_match else table_html

            for row_match in row_pattern.finditer(search_html):
                row_id = row_match.group(1) or ""
                row_html = row_match.group(2)

                tds = td_pattern.findall(row_html)
                if len(tds) < 3:
                    continue

                cells = [tag_strip.sub("", td).strip() for td in tds]

                # Skip header-like rows
                if any(
                    h in " ".join(cells).lower()
                    for h in ["stt", "ký hiệu", "số hóa đơn"]
                ):
                    if "ký hiệu" in " ".join(cells).lower():
                        continue

                # Extract data based on column mapping
                invoice = self._extract_invoice_from_cells(cells, col_map, row_id)
                if invoice:
                    invoices.append(invoice)

            _logger.info("Parsed %d invoices from HTML table", len(invoices))

        except Exception as e:
            _logger.error("Error parsing invoice HTML: %s", e, exc_info=True)

        # Check pagination
        has_more = len(invoices) >= page_size

        # Also check for pagination links
        if "next" in html.lower() or "page=%d" % (page + 1) in html:
            has_more = True

        return {
            "invoices": invoices,
            "total": len(invoices),
            "has_more": has_more,
        }

    def _detect_column_map(self, headers):
        """
        Detect column positions from header text.

        Returns:
            dict: Mapping of field names to column indices.
        """
        col_map = {}

        for i, h in enumerate(headers):
            h_lower = h.lower().strip()
            if not h_lower:
                continue

            # STT / No.
            if h_lower in ("stt", "no", "no.", "#"):
                col_map["stt"] = i
            # Ký hiệu / Symbol / Series
            elif "ký hiệu" in h_lower or "symbol" in h_lower or "series" in h_lower:
                col_map["series"] = i
            # Số hóa đơn / Invoice Number
            elif (
                "số" in h_lower and ("hóa đơn" in h_lower or "hd" in h_lower)
            ) or "invoice" in h_lower and "number" in h_lower:
                col_map["invoice_number"] = i
            elif "số" in h_lower and "hóa" not in h_lower:
                col_map.setdefault("invoice_number", i)
            # Ngày / Date
            elif "ngày" in h_lower or "date" in h_lower:
                col_map["date"] = i
            # Tên người mua / Buyer name
            elif "người mua" in h_lower or "buyer" in h_lower or "khách" in h_lower:
                if "mst" in h_lower or "mã số" in h_lower or "tax" in h_lower:
                    col_map["buyer_tax"] = i
                else:
                    col_map["buyer_name"] = i
            # MST / Tax code
            elif "mst" in h_lower or "mã số thuế" in h_lower or "tax" in h_lower:
                col_map["buyer_tax"] = i
            # Tổng tiền / Total / Amount
            elif (
                "tổng" in h_lower
                or "tiền" in h_lower
                or "total" in h_lower
                or "amount" in h_lower
                or "thành tiền" in h_lower
            ):
                col_map["total_amount"] = i
            # Trạng thái / Status
            elif "trạng thái" in h_lower or "status" in h_lower:
                col_map["status"] = i
            # Tên người bán / Seller
            elif "người bán" in h_lower or "seller" in h_lower:
                col_map["seller_name"] = i

        # If no explicit mapping found, use default positions
        if not col_map:
            _logger.info("Using default column positions (no headers matched)")
            col_map = {
                "stt": 0,
                "series": 1,
                "invoice_number": 2,
                "date": 3,
                "buyer_name": 4,
                "buyer_tax": 5,
                "total_amount": 6,
                "status": 7,
            }

        return col_map

    def _extract_invoice_from_cells(self, cells, col_map, row_id=""):
        """
        Extract invoice data from table cells using column mapping.

        Args:
            cells (list): List of cell text values.
            col_map (dict): Column position mapping.
            row_id (str): Row ID attribute value.

        Returns:
            dict: Invoice data, or None if invalid.
        """
        def safe_get(idx):
            if idx is not None and 0 <= idx < len(cells):
                return cells[idx].strip()
            return ""

        invoice_number = safe_get(col_map.get("invoice_number"))
        series = safe_get(col_map.get("series"))
        date_str = safe_get(col_map.get("date"))
        buyer_name = safe_get(col_map.get("buyer_name"))
        buyer_tax = safe_get(col_map.get("buyer_tax"))
        seller_name = safe_get(col_map.get("seller_name"))
        amount_str = safe_get(col_map.get("total_amount"))
        status = safe_get(col_map.get("status"))

        # Need at least invoice number or row_id
        if not invoice_number and not row_id:
            return None

        # Build a unique ID
        inv_id = row_id or invoice_number

        return {
            "id": inv_id,
            "invoice_number": invoice_number or inv_id,
            "series": series,
            "invoice_date": date_str,
            "buyer_name": buyer_name,
            "buyer_tax_code": buyer_tax,
            "seller_name": seller_name,
            "total_amount": self._parse_amount(amount_str),
            "status": status,
        }

    def _parse_invoice_list_json(self, data):
        """Parse JSON response from the invoice list endpoint."""
        invoices = []

        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            raw_list = (
                data.get("data", [])
                or data.get("items", [])
                or data.get("invoices", [])
                or data.get("Data", [])
                or []
            )
        else:
            raw_list = []

        for item in raw_list:
            invoice = self._normalize_invoice_json(item)
            if invoice:
                invoices.append(invoice)

        total = (
            data.get("total", len(invoices))
            if isinstance(data, dict)
            else len(invoices)
        )

        return {
            "invoices": invoices,
            "total": total,
            "has_more": len(invoices) >= 50,
        }

    def _normalize_invoice_json(self, raw):
        """Normalize a raw invoice dict from JSON API response."""
        if not raw:
            return None

        invoice_id = (
            raw.get("id") or raw.get("Id")
            or raw.get("invoiceId") or raw.get("InvoiceId")
            or ""
        )
        invoice_number = (
            raw.get("invoiceNumber") or raw.get("InvoiceNumber")
            or raw.get("invoice_number") or raw.get("SoHoaDon")
            or str(invoice_id)
        )
        invoice_date = (
            raw.get("invoiceDate") or raw.get("InvoiceDate")
            or raw.get("invoice_date") or raw.get("NgayHoaDon")
            or ""
        )
        total_amount = float(
            raw.get("totalAmount") or raw.get("TotalAmount")
            or raw.get("total_amount") or raw.get("TongTien")
            or 0
        )
        buyer_name = (
            raw.get("buyerName") or raw.get("BuyerName")
            or raw.get("buyer_name") or ""
        )
        buyer_tax = (
            raw.get("buyerTaxCode") or raw.get("BuyerTaxCode")
            or raw.get("buyer_tax_code") or ""
        )
        seller_name = (
            raw.get("sellerName") or raw.get("SellerName")
            or raw.get("seller_name") or ""
        )
        status = raw.get("status") or raw.get("Status") or ""

        return {
            "id": str(invoice_id),
            "invoice_number": str(invoice_number),
            "invoice_date": str(invoice_date),
            "total_amount": total_amount,
            "buyer_name": str(buyer_name),
            "buyer_tax_code": str(buyer_tax),
            "seller_name": str(seller_name),
            "status": str(status),
        }

    def _parse_amount(self, amount_str):
        """Parse a Vietnamese-formatted amount string to float."""
        if not amount_str:
            return 0.0
        try:
            # Remove thousands separators (dots) and replace decimal comma
            cleaned = str(amount_str).replace(".", "").replace(",", ".").strip()
            # Remove non-numeric chars except dot and minus
            cleaned = re.sub(r"[^\d.\-]", "", cleaned)
            return float(cleaned) if cleaned else 0.0
        except (ValueError, AttributeError):
            return 0.0

    # ------------------------------------------------------------------
    # File Download
    # ------------------------------------------------------------------

    def download_invoice_files(self, invoice_ids, allow_pdf=True, allow_xml=True):
        """
        Download invoice files (PDF/XML) as a ZIP archive.

        Args:
            invoice_ids (list): List of invoice IDs to download.
            allow_pdf (bool): Include PDF files.
            allow_xml (bool): Include XML files.

        Returns:
            bytes: ZIP file content, or None on failure.
        """
        if not self._authenticated:
            raise ValueError("Not authenticated.")

        if not invoice_ids:
            return None

        _logger.info(
            "Downloading files for %d invoices (PDF=%s, XML=%s)",
            len(invoice_ids), allow_pdf, allow_xml,
        )

        payload = {
            "data": invoice_ids,
            "allowPdf": allow_pdf,
            "allowXml": allow_xml,
        }

        try:
            response = self._session.post(
                self._url(INVOICE_DOWNLOAD_PATH),
                json=payload,
                timeout=(CONNECT_TIMEOUT, 120),
                headers={
                    "Accept": "application/zip, application/octet-stream, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/json",
                    "Referer": self._url(INVOICE_LIST_PATH),
                },
            )

            if response.status_code == 200 and len(response.content) > 100:
                _logger.info(
                    "Downloaded %d bytes for %d invoices",
                    len(response.content), len(invoice_ids),
                )
                return response.content
            else:
                _logger.warning(
                    "Download response: HTTP %d, size: %d bytes",
                    response.status_code, len(response.content),
                )
                return None

        except requests.RequestException as e:
            _logger.error("Download request failed: %s", e)
            raise

    def logout(self):
        """Log out from the portal."""
        try:
            self._session.get(
                self._url(LOGOUT_PATH),
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            pass
        finally:
            self._authenticated = False
            self._auth_time = None
            self._csrf_token = None
            self._session.cookies.clear()
            _logger.info("Logged out from Grab e-invoice portal")
