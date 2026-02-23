# -*- coding: utf-8 -*-
"""
Grab E-Invoice Session Manager
================================
Handles authentication and session management for vn.einvoice.grab.com portal.

The portal uses:
  - ASP.NET MVC with CSRF token (__RequestVerificationToken)
  - Image-based CAPTCHA (CaptchaHash cookie stores MD5 of the expected answer)
  - Cookie-based session (.ASPXAUTH)

Flow:
  1. GET /tai-khoan/dang-nhap  -> receive CSRF token + session cookie
  2. GET /Captcha/Show         -> receive CAPTCHA image + CaptchaHash cookie
  3. POST /tai-khoan/dang-nhap -> submit credentials + CAPTCHA answer
  4. Use authenticated session for subsequent API calls
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
INVOICE_LIST_PATH = "/Invoice/GetList"
INVOICE_DOWNLOAD_PATH = "/Invoice/DowloadData"
INVOICE_SEARCH_PATH = "/Invoice/Search"

# Timeout settings
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)


class GrabEInvoiceSession:
    """
    Manages an authenticated session with the Grab e-invoice portal.

    Usage::

        session = GrabEInvoiceSession(username, password, base_url)
        captcha_b64 = session.get_captcha_image()
        # Show captcha to user, get answer
        success = session.login(captcha_answer)
        if success:
            invoices = session.fetch_invoices(date_from, date_to)
    """

    def __init__(self, username, password, base_url=None):
        """
        Initialize the session manager.

        Args:
            username (str): Portal username (Tài khoản).
            password (str): Portal password (Mật khẩu).
            base_url (str): Override base URL (default: GRAB_PORTAL_BASE).
        """
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

        # Retry on transient errors
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Mimic a real browser to avoid bot detection
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        return session

    def _url(self, path):
        """Build full URL from path."""
        return "%s%s" % (self.base_url, path)

    def prepare_login(self):
        """
        Load the login page to obtain the CSRF token and session cookie.

        Returns:
            bool: True if preparation succeeded.

        Raises:
            requests.RequestException: On network errors.
        """
        try:
            _logger.info("Preparing Grab e-invoice login session...")
            response = self._session.get(
                self._url(LOGIN_PATH),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            # Extract CSRF token from the hidden input field
            match = re.search(
                r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"',
                response.text,
            )
            if not match:
                # Try alternate pattern
                match = re.search(
                    r'__RequestVerificationToken.*?value="([^"]+)"',
                    response.text,
                )

            if match:
                self._csrf_token = match.group(1)
                _logger.debug("CSRF token obtained: %s...", self._csrf_token[:20])
            else:
                _logger.warning("Could not extract CSRF token from login page")
                # Try to get from cookie
                for cookie in self._session.cookies:
                    if "RequestVerificationToken" in cookie.name:
                        self._csrf_token = cookie.value
                        break

            return True

        except requests.RequestException as e:
            _logger.error("Failed to prepare login session: %s", e)
            raise

    def get_captcha_image(self):
        """
        Fetch the CAPTCHA image from the portal.

        Returns:
            bytes: Raw PNG image bytes, or None on failure.
        """
        try:
            _logger.info("Fetching CAPTCHA image from Grab portal...")
            response = self._session.get(
                self._url(CAPTCHA_PATH),
                timeout=REQUEST_TIMEOUT,
                headers={
                    "Referer": self._url(LOGIN_PATH),
                    "Accept": "image/png,image/webp,*/*",
                },
            )

            if response.status_code == 200 and response.headers.get(
                "content-type", ""
            ).startswith("image/"):
                _logger.info(
                    "CAPTCHA image fetched: %d bytes", len(response.content)
                )
                return response.content
            else:
                _logger.warning(
                    "Unexpected CAPTCHA response: HTTP %d, Content-Type: %s",
                    response.status_code,
                    response.headers.get("content-type", "unknown"),
                )
                return None

        except requests.RequestException as e:
            _logger.error("Failed to fetch CAPTCHA: %s", e)
            return None

    def get_captcha_image_b64(self):
        """
        Fetch the CAPTCHA image and return as base64-encoded string.

        Returns:
            str: Base64-encoded PNG image, or empty string on failure.
        """
        raw = self.get_captcha_image()
        if raw:
            return base64.b64encode(raw).decode("utf-8")
        return ""

    def login(self, captcha_answer):
        """
        Attempt to log in to the Grab e-invoice portal.

        Args:
            captcha_answer (str): The text answer to the CAPTCHA challenge.

        Returns:
            bool: True if login was successful.

        Raises:
            ValueError: If CSRF token is not available (call prepare_login first).
            requests.RequestException: On network errors.
        """
        if not self._csrf_token:
            raise ValueError(
                "CSRF token not available. Call prepare_login() first."
            )

        _logger.info(
            "Attempting Grab e-invoice login for user: %s", self.username
        )

        payload = {
            "__RequestVerificationToken": self._csrf_token,
            "UserName": self.username,
            "Password": self.password,
            "captch": captcha_answer,
        }

        try:
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

            # Check for successful login indicators
            # After successful login, the portal redirects to the invoice list page
            final_url = response.url
            response_text = response.text

            if (
                "/tai-khoan/dang-nhap" not in final_url
                and "dang-nhap" not in final_url.lower()
                and response.status_code == 200
            ):
                # Check for error messages in the response
                if "Tài khoản hoặc mật khẩu không đúng" in response_text:
                    _logger.warning("Login failed: incorrect username or password")
                    return False
                if "Mã kiểm tra không đúng" in response_text or "captcha" in response_text.lower():
                    _logger.warning("Login failed: incorrect CAPTCHA")
                    return False

                self._authenticated = True
                self._auth_time = datetime.now()
                _logger.info(
                    "Grab e-invoice login successful. Redirected to: %s", final_url
                )
                return True

            # Check if we're still on the login page (indicates failure)
            if "dang-nhap" in final_url.lower():
                # Look for error messages
                if "Mã kiểm tra" in response_text:
                    _logger.warning("Login failed: CAPTCHA error")
                elif "mật khẩu" in response_text.lower():
                    _logger.warning("Login failed: credential error")
                else:
                    _logger.warning(
                        "Login failed: still on login page after POST"
                    )
                return False

            # Assume success if we got a 200 and are not on login page
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info("Grab e-invoice login appears successful")
            return True

        except requests.RequestException as e:
            _logger.error("Login request failed: %s", e)
            raise

    def is_authenticated(self):
        """
        Check if the session is currently authenticated.

        Returns:
            bool: True if authenticated and session is likely still valid.
        """
        if not self._authenticated or not self._auth_time:
            return False
        # Sessions typically expire after 30 minutes of inactivity
        elapsed = datetime.now() - self._auth_time
        if elapsed > timedelta(minutes=25):
            _logger.info("Session may have expired (age: %s)", elapsed)
            self._authenticated = False
            return False
        return True

    def fetch_invoices(self, date_from=None, date_to=None, page=1, page_size=50):
        """
        Fetch the invoice list from the portal.

        Args:
            date_from (str): Start date in 'dd/MM/yyyy' format (Vietnamese format).
            date_to (str): End date in 'dd/MM/yyyy' format.
            page (int): Page number (1-based).
            page_size (int): Number of records per page.

        Returns:
            dict: Parsed response containing invoice list and pagination info.
                  Keys: 'invoices' (list), 'total' (int), 'has_more' (bool).

        Raises:
            ValueError: If not authenticated.
            requests.RequestException: On network errors.
        """
        if not self.is_authenticated():
            raise ValueError(
                "Not authenticated. Call prepare_login() + login() first."
            )

        # Default date range: last 30 days
        if not date_to:
            date_to = datetime.now().strftime("%d/%m/%Y")
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")

        _logger.info(
            "Fetching Grab invoices: %s to %s (page %d)", date_from, date_to, page
        )

        # Try JSON API first (AJAX endpoint)
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "page": page,
            "pageSize": page_size,
        }

        try:
            # First try the AJAX/JSON endpoint
            response = self._session.get(
                self._url(INVOICE_LIST_PATH),
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self._url("/hoa-don/danh-sach"),
                },
            )

            content_type = response.headers.get("content-type", "")

            if "application/json" in content_type or "text/json" in content_type:
                data = response.json()
                return self._parse_invoice_list_json(data)
            else:
                # Response is HTML - parse the table
                _logger.debug(
                    "Invoice list returned HTML (HTTP %d), parsing table...",
                    response.status_code,
                )
                return self._parse_invoice_list_html(response.text, page, page_size)

        except requests.RequestException as e:
            _logger.error("Failed to fetch invoice list: %s", e)
            raise

    def _parse_invoice_list_json(self, data):
        """
        Parse JSON response from the invoice list endpoint.

        Args:
            data (dict or list): Parsed JSON response.

        Returns:
            dict: Normalized invoice list with keys 'invoices', 'total', 'has_more'.
        """
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
            invoice = self._normalize_invoice(item)
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

    def _parse_invoice_list_html(self, html, page, page_size):
        """
        Parse HTML table response from the invoice list endpoint.

        Args:
            html (str): Raw HTML content.
            page (int): Current page number.
            page_size (int): Page size.

        Returns:
            dict: Normalized invoice list with keys 'invoices', 'total', 'has_more'.
        """
        invoices = []

        try:
            # Parse table rows using regex (avoid BeautifulSoup dependency)
            # Look for table rows with invoice data
            # Pattern: <tr id="...">...<td>invoice_number</td>...<td>date</td>...<td>amount</td>...
            row_pattern = re.compile(
                r'<tr[^>]*id="([^"]+)"[^>]*>(.*?)</tr>',
                re.DOTALL | re.IGNORECASE,
            )
            td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
            tag_strip = re.compile(r'<[^>]+>')

            for row_match in row_pattern.finditer(html):
                row_id = row_match.group(1)
                row_html = row_match.group(2)

                tds = td_pattern.findall(row_html)
                if len(tds) < 3:
                    continue

                # Clean HTML tags from cell content
                cells = [tag_strip.sub("", td).strip() for td in tds]

                # Try to extract invoice data from cells
                # Typical columns: [checkbox, invoice_number, date, buyer, seller, amount, status, ...]
                invoice = {
                    "id": row_id,
                    "invoice_number": cells[1] if len(cells) > 1 else row_id,
                    "date": cells[2] if len(cells) > 2 else "",
                    "buyer_name": cells[3] if len(cells) > 3 else "",
                    "seller_name": cells[4] if len(cells) > 4 else "",
                    "total_amount": self._parse_amount(cells[5] if len(cells) > 5 else "0"),
                    "status": cells[6] if len(cells) > 6 else "",
                    "raw_id": row_id,
                }
                invoices.append(invoice)

            _logger.info("Parsed %d invoices from HTML table", len(invoices))

        except Exception as e:
            _logger.error("Error parsing invoice HTML: %s", e)

        return {
            "invoices": invoices,
            "total": len(invoices),
            "has_more": len(invoices) >= page_size,
        }

    def _normalize_invoice(self, raw):
        """
        Normalize a raw invoice dict from the API response.

        Args:
            raw (dict): Raw invoice data from API.

        Returns:
            dict: Normalized invoice dict, or None if invalid.
        """
        if not raw:
            return None

        # Map various possible field names to standard names
        invoice_id = (
            raw.get("id")
            or raw.get("Id")
            or raw.get("invoiceId")
            or raw.get("InvoiceId")
            or raw.get("invoice_id")
            or ""
        )
        invoice_number = (
            raw.get("invoiceNumber")
            or raw.get("InvoiceNumber")
            or raw.get("invoice_number")
            or raw.get("so_hoa_don")
            or raw.get("SoHoaDon")
            or str(invoice_id)
        )
        invoice_date = (
            raw.get("invoiceDate")
            or raw.get("InvoiceDate")
            or raw.get("invoice_date")
            or raw.get("ngay_hoa_don")
            or raw.get("NgayHoaDon")
            or raw.get("date")
            or ""
        )
        total_amount = float(
            raw.get("totalAmount")
            or raw.get("TotalAmount")
            or raw.get("total_amount")
            or raw.get("tong_tien")
            or raw.get("TongTien")
            or raw.get("amount")
            or 0
        )
        buyer_name = (
            raw.get("buyerName")
            or raw.get("BuyerName")
            or raw.get("buyer_name")
            or raw.get("ten_nguoi_mua")
            or ""
        )
        buyer_tax = (
            raw.get("buyerTaxCode")
            or raw.get("BuyerTaxCode")
            or raw.get("buyer_tax_code")
            or raw.get("ma_so_thue_nguoi_mua")
            or ""
        )
        seller_name = (
            raw.get("sellerName")
            or raw.get("SellerName")
            or raw.get("seller_name")
            or raw.get("ten_nguoi_ban")
            or ""
        )
        status = (
            raw.get("status")
            or raw.get("Status")
            or raw.get("trang_thai")
            or ""
        )

        return {
            "id": str(invoice_id),
            "invoice_number": str(invoice_number),
            "invoice_date": str(invoice_date),
            "total_amount": total_amount,
            "buyer_name": str(buyer_name),
            "buyer_tax_code": str(buyer_tax),
            "seller_name": str(seller_name),
            "status": str(status),
            "raw": raw,
        }

    def _parse_amount(self, amount_str):
        """Parse a Vietnamese-formatted amount string to float."""
        try:
            # Remove thousands separators (dots) and replace decimal comma with dot
            cleaned = amount_str.replace(".", "").replace(",", ".").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return 0.0

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
        if not self.is_authenticated():
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
                timeout=(CONNECT_TIMEOUT, 120),  # Longer timeout for downloads
                headers={
                    "Accept": "application/zip, application/octet-stream, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self._url("/hoa-don/danh-sach"),
                },
            )

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "zip" in content_type or "octet-stream" in content_type:
                    _logger.info(
                        "Downloaded %d bytes for %d invoices",
                        len(response.content), len(invoice_ids),
                    )
                    return response.content
                else:
                    _logger.warning(
                        "Unexpected content type for download: %s", content_type
                    )
                    return response.content
            else:
                _logger.error(
                    "Download failed: HTTP %d - %s",
                    response.status_code, response.text[:200],
                )
                return None

        except requests.RequestException as e:
            _logger.error("Download request failed: %s", e)
            raise

    def logout(self):
        """Log out from the portal and clear the session."""
        try:
            self._session.get(
                self._url("/tai-khoan/dang-xuat"),
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
