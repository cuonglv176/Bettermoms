# -*- coding: utf-8 -*-
"""
SPV Tracuuhoadon E-Invoice Session Manager
==========================================
Handles authentication and invoice fetching from the SPV Tracuuhoadon portal
(https://spv.tracuuhoadon.online).

Authentication flow:
  1. GET /dang-nhap  → extract __RequestVerificationToken, nonce, and session cookies
  2. GET /Captcha    → download CAPTCHA image
  3. POST /dang-nhap → submit credentials + CAPTCHA → receive auth cookies
  4. GET /hoa-don    → fetch invoice list (paginated)

CAPTCHA solving:
  - Manual: caller provides the text answer
  - Auto:   uses Google Gemini Vision API to read the CAPTCHA image

This module mirrors the design of grab_session.py to maintain consistency.
"""

import base64
import io
import json
import logging
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)

# ---- Constants ---------------------------------------------------------------
DEFAULT_BASE_URL = "https://spv.tracuuhoadon.online"
LOGIN_PATH = "/dang-nhap"
CAPTCHA_PATH = "/Captcha"
INVOICE_LIST_PATH = "/hoa-don"
INVOICE_API_PATH = "/HoaDon/GetList"

SESSION_TIMEOUT_MINUTES = 25
REQUEST_TIMEOUT = 30
MAX_LOGIN_ATTEMPTS = 5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

HEADERS_BASE = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


class SpvEInvoiceSession:
    """
    Manages a login session with the SPV Tracuuhoadon e-invoice portal.

    Usage (auto-login)::

        session = SpvEInvoiceSession(username="maKh", password="pass")
        if session.auto_login():
            invoices = session.fetch_invoices(date_from="01/01/2025", date_to="31/12/2025")

    Usage (manual CAPTCHA)::

        session = SpvEInvoiceSession(username="maKh", password="pass")
        session.prepare_login()
        captcha_b64 = session.get_captcha_image_b64()
        # ... show image to user, get answer ...
        if session.login(captcha_answer):
            invoices = session.fetch_invoices(...)
    """

    def __init__(self, username, password, base_url=None):
        self.username = username
        self.password = password
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

        self._session = requests.Session()
        self._session.headers.update(HEADERS_BASE)

        self._csrf_token = None
        self._nonce = None
        self._captcha_image_bytes = None
        self._authenticated = False
        self._auth_time = None

        self.last_error = None
        self.is_account_locked = False

    # =========================================================================
    # Public API
    # =========================================================================

    def prepare_login(self):
        """
        Load the login page to extract CSRF token, nonce, and session cookies.
        Must be called before get_captcha_image_b64() and login().
        """
        url = "%s%s" % (self.base_url, LOGIN_PATH)
        _logger.info("SPV: Loading login page: %s", url)

        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            self.last_error = "Failed to load login page: %s" % e
            _logger.error("SPV: %s", self.last_error)
            raise

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract __RequestVerificationToken
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        if token_input:
            self._csrf_token = token_input.get("value", "")
            _logger.debug("SPV: CSRF token extracted (len=%d)", len(self._csrf_token or ""))
        else:
            _logger.warning("SPV: __RequestVerificationToken not found on login page")
            self._csrf_token = ""

        # Extract nonce (hidden field or meta tag)
        nonce_input = soup.find("input", {"name": "nonce"})
        if nonce_input:
            self._nonce = nonce_input.get("value", "")
        else:
            # Try meta tag
            nonce_meta = soup.find("meta", {"name": "nonce"})
            if nonce_meta:
                self._nonce = nonce_meta.get("content", "")
            else:
                self._nonce = ""

        _logger.debug("SPV: nonce=%r", self._nonce)

    def get_captcha_image_b64(self):
        """
        Download the CAPTCHA image from the portal.

        Returns:
            str: Base64-encoded PNG image, or None on failure.
        """
        url = "%s%s" % (self.base_url, CAPTCHA_PATH)
        _logger.info("SPV: Fetching CAPTCHA image from %s", url)

        try:
            resp = self._session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"Referer": "%s%s" % (self.base_url, LOGIN_PATH)},
            )
            resp.raise_for_status()
            self._captcha_image_bytes = resp.content
            b64 = base64.b64encode(resp.content).decode("utf-8")
            _logger.debug("SPV: CAPTCHA image fetched (%d bytes)", len(resp.content))
            return b64
        except requests.RequestException as e:
            self.last_error = "Failed to fetch CAPTCHA: %s" % e
            _logger.error("SPV: %s", self.last_error)
            return None

    def login(self, captcha_answer):
        """
        Submit login form with the provided CAPTCHA answer.

        Args:
            captcha_answer (str): The text answer for the current CAPTCHA.

        Returns:
            bool: True if login succeeded, False otherwise.
        """
        if not self._csrf_token and not self._nonce:
            _logger.warning("SPV: prepare_login() not called; loading login page now...")
            self.prepare_login()

        url = "%s%s" % (self.base_url, LOGIN_PATH)
        _logger.info("SPV: Submitting login for user '%s'...", self.username)

        payload = {
            "__RequestVerificationToken": self._csrf_token or "",
            "maKh": self.username,
            "pass": self.password,
            "captchaCode": captcha_answer.strip() if captcha_answer else "",
        }
        if self._nonce:
            payload["nonce"] = self._nonce

        headers = {
            "Referer": url,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
        }

        try:
            resp = self._session.post(
                url,
                data=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except requests.RequestException as e:
            self.last_error = "Login request failed: %s" % e
            _logger.error("SPV: %s", self.last_error)
            return False

        # Check for account lock
        if "b\u1ecb kh\u00f3a" in resp.text.lower() or "locked" in resp.text.lower():
            self.is_account_locked = True
            self.last_error = "Account is locked."
            _logger.error("SPV: Account '%s' is locked!", self.username)
            return False

        # Check for login failure indicators
        failure_indicators = [
            "sai m\u00e3 captcha",
            "captcha kh\u00f4ng \u0111\u00fang",
            "sai t\u00ean \u0111\u0103ng nh\u1eadp",
            "sai m\u1eadt kh\u1ea9u",
            "th\u00f4ng tin \u0111\u0103ng nh\u1eadp kh\u00f4ng \u0111\u00fang",
            "invalid",
            "incorrect",
            "dang-nhap",  # still on login page
        ]
        resp_lower = resp.text.lower()
        # If redirected away from login page, consider success
        final_url = resp.url.rstrip("/")
        login_url = ("%s%s" % (self.base_url, LOGIN_PATH)).rstrip("/")

        if final_url == login_url:
            # Still on login page — check for error messages
            for indicator in failure_indicators:
                if indicator in resp_lower:
                    self.last_error = "Login failed: found '%s' in response" % indicator
                    _logger.warning("SPV: Login failed for '%s': %s", self.username, self.last_error)
                    return False
            # On login page but no clear error — might be a redirect issue
            self.last_error = "Login failed: still on login page after POST"
            _logger.warning("SPV: %s", self.last_error)
            return False

        # Verify we have a valid session by checking for auth cookie
        auth_cookies = [
            c.name for c in self._session.cookies
            if any(kw in c.name.lower() for kw in [".aspxauth", "auth", "session", "aspnet"])
        ]
        if not auth_cookies:
            # Try to verify by accessing a protected page
            _logger.debug("SPV: No obvious auth cookie found, verifying session...")
            if not self.check_session_valid():
                self.last_error = "Login appeared to succeed but session check failed."
                _logger.warning("SPV: %s", self.last_error)
                return False

        self._authenticated = True
        self._auth_time = datetime.now()
        _logger.info("SPV: Login successful for user '%s'", self.username)
        return True

    def auto_login(self, gemini_api_key=None, openai_api_key=None, max_attempts=None):
        """
        Attempt fully automatic login by solving CAPTCHA with Google Gemini Vision API.

        Args:
            gemini_api_key (str): Optional Google Gemini API key. Falls back to GEMINI_API_KEY env var.
            openai_api_key (str): Deprecated. Use gemini_api_key instead.
            max_attempts (int): Maximum number of CAPTCHA attempts.

        Returns:
            bool: True if login succeeded within max_attempts.
        """
        import os
        max_attempts = max_attempts or MAX_LOGIN_ATTEMPTS
        api_key = gemini_api_key or openai_api_key or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

        if not api_key:
            self.last_error = (
                "Google Gemini API key not provided and GEMINI_API_KEY env var not set. "
                "Cannot auto-solve CAPTCHA."
            )
            _logger.error("SPV: %s", self.last_error)
            return False

        for attempt in range(1, max_attempts + 1):
            _logger.info(
                "SPV: Auto-login attempt %d/%d for user '%s'",
                attempt, max_attempts, self.username,
            )

            try:
                self.prepare_login()
                captcha_b64 = self.get_captcha_image_b64()

                if not captcha_b64:
                    _logger.warning("SPV: Could not fetch CAPTCHA image (attempt %d)", attempt)
                    time.sleep(2)
                    continue

                captcha_answer = self._solve_captcha_with_gemini(captcha_b64, api_key)
                if not captcha_answer:
                    _logger.warning("SPV: Gemini returned empty CAPTCHA answer (attempt %d)", attempt)
                    time.sleep(1)
                    continue

                _logger.info(
                    "SPV: Gemini CAPTCHA answer: '%s' (attempt %d)",
                    captcha_answer, attempt,
                )

                if self.login(captcha_answer):
                    _logger.info(
                        "SPV: Auto-login succeeded on attempt %d/%d",
                        attempt, max_attempts,
                    )
                    return True

                if self.is_account_locked:
                    _logger.error("SPV: Account locked, stopping auto-login.")
                    return False

                _logger.warning(
                    "SPV: Login attempt %d failed: %s", attempt, self.last_error
                )
                time.sleep(2 * attempt)

            except Exception as e:
                _logger.warning(
                    "SPV: Exception on auto-login attempt %d: %s", attempt, e
                )
                self.last_error = str(e)
                time.sleep(2)

        _logger.error(
            "SPV: All %d auto-login attempts failed for user '%s'",
            max_attempts, self.username,
        )
        return False

    def check_session_valid(self):
        """
        Verify the current session is still authenticated.

        Returns:
            bool: True if session is valid.
        """
        url = "%s%s" % (self.base_url, INVOICE_LIST_PATH)
        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            final_url = resp.url.rstrip("/")
            login_url = ("%s%s" % (self.base_url, LOGIN_PATH)).rstrip("/")
            if final_url == login_url or resp.status_code == 401:
                _logger.debug("SPV: Session check failed — redirected to login page")
                return False
            return True
        except requests.RequestException as e:
            _logger.warning("SPV: Session check error: %s", e)
            return False

    def fetch_invoices(self, date_from=None, date_to=None, page=1, page_size=50):
        """
        Fetch invoice list from the SPV portal.

        Args:
            date_from (str): Start date in dd/MM/yyyy format.
            date_to (str): End date in dd/MM/yyyy format.
            page (int): Page number (1-based).
            page_size (int): Number of records per page.

        Returns:
            dict: {
                "invoices": [...],
                "has_more": bool,
                "total": int,
            }

        Raises:
            ValueError: If the session has expired.
        """
        if not self._authenticated:
            raise ValueError("Not authenticated. Call login() or auto_login() first.")

        # Try JSON API endpoint first
        url = "%s%s" % (self.base_url, INVOICE_API_PATH)
        _logger.info(
            "SPV: Fetching invoices page %d (from=%s, to=%s)",
            page, date_from, date_to,
        )

        payload = {
            "tuNgay": date_from or "",
            "denNgay": date_to or "",
            "trang": page,
            "soLuong": page_size,
        }

        headers = {
            "Referer": "%s%s" % (self.base_url, INVOICE_LIST_PATH),
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        try:
            resp = self._session.post(
                url,
                data=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            # Check for session expiry
            if resp.status_code == 401 or (
                resp.status_code in (200, 302)
                and LOGIN_PATH in resp.url
            ):
                self._authenticated = False
                raise ValueError("SPV session expired. Re-login required.")

            resp.raise_for_status()

            try:
                data = resp.json()
            except ValueError:
                # Response is not JSON — try HTML parsing
                _logger.debug("SPV: JSON parse failed, trying HTML parsing...")
                return self._parse_invoice_html(resp.text, page, page_size)

            return self._normalize_invoice_response(data, page, page_size)

        except ValueError:
            raise
        except requests.RequestException as e:
            _logger.error("SPV: Invoice fetch error (page %d): %s", page, e)
            raise

    def get_session_cookie(self):
        """
        Return the primary session cookie value for storage.

        Returns:
            str: Cookie value, or None.
        """
        # Try common ASP.NET auth cookie names
        for name in [".ASPXAUTH", "ASP.NET_SessionId", "ASPXAUTH"]:
            val = self._session.cookies.get(name)
            if val:
                return val
        # Return first available cookie
        for c in self._session.cookies:
            if c.value:
                return c.value
        return None

    def restore_session(self, cookies_json):
        """
        Restore a previously saved session from a JSON-encoded cookies dict.

        Args:
            cookies_json (str): JSON string of {name: value} cookie pairs.
        """
        try:
            cookies = json.loads(cookies_json or "{}")
            for name, value in cookies.items():
                self._session.cookies.set(name, value)
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.debug("SPV: Session restored from %d cookies", len(cookies))
        except Exception as e:
            _logger.warning("SPV: Failed to restore session: %s", e)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _solve_captcha_with_gemini(self, captcha_b64, api_key):
        """
        Use Google Gemini Vision API to read the CAPTCHA text from a base64 image.

        Args:
            captcha_b64 (str): Base64-encoded image.
            api_key (str): Google Gemini API key.

        Returns:
            str: Recognized CAPTCHA text, or empty string on failure.
        """
        try:
            import google.generativeai as genai
            import PIL.Image
            import io as _io

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

            image_bytes = base64.b64decode(captcha_b64)
            image = PIL.Image.open(_io.BytesIO(image_bytes))

            prompt = (
                "This is a CAPTCHA image from a Vietnamese e-invoice portal. "
                "Please read the text or numbers shown in the image carefully. "
                "Return ONLY the exact characters you see, with no spaces, "
                "no punctuation, no explanation. "
                "If the CAPTCHA contains both letters and numbers, include all of them. "
                "Common Vietnamese CAPTCHA formats: 4-6 alphanumeric characters."
            )

            response = model.generate_content([prompt, image])
            answer = response.text.strip()
            # Clean: remove spaces and common noise characters
            answer = re.sub(r"[\s\.\,\!\?\-\_]", "", answer)
            _logger.debug("SPV: Gemini CAPTCHA response: '%s'", answer)
            return answer

        except ImportError:
            _logger.warning(
                "SPV: google-generativeai or Pillow not installed. "
                "Run: pip install google-generativeai pillow"
            )
            return ""
        except Exception as e:
            _logger.warning("SPV: Gemini CAPTCHA solving failed: %s", e)
            return ""

    def _solve_captcha_with_openai(self, captcha_b64, api_key):
        """Deprecated: Use _solve_captcha_with_gemini() instead."""
        return self._solve_captcha_with_gemini(captcha_b64, api_key)

    def _normalize_invoice_response(self, data, page, page_size):
        """
        Normalize various JSON response formats into a standard dict.

        Returns:
            dict: {"invoices": [...], "has_more": bool, "total": int}
        """
        invoices = []
        total = 0
        has_more = False

        # Format 1: {"data": [...], "total": N}
        if isinstance(data, dict) and "data" in data:
            raw_list = data.get("data", [])
            total = int(data.get("total", data.get("tongSo", len(raw_list))))
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 2: {"items": [...], "totalCount": N}
        elif isinstance(data, dict) and "items" in data:
            raw_list = data.get("items", [])
            total = int(data.get("totalCount", data.get("total", len(raw_list))))
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 3: {"hoaDons": [...], "tongSo": N}
        elif isinstance(data, dict) and "hoaDons" in data:
            raw_list = data.get("hoaDons", [])
            total = int(data.get("tongSo", len(raw_list)))
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 4: direct list
        elif isinstance(data, list):
            raw_list = data
            total = len(raw_list)
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 5: {"success": True, "result": {...}}
        elif isinstance(data, dict) and "result" in data:
            return self._normalize_invoice_response(data["result"], page, page_size)

        has_more = (page * page_size) < total

        return {
            "invoices": invoices,
            "has_more": has_more,
            "total": total,
        }

    def _normalize_invoice_item(self, item):
        """
        Normalize a single invoice item dict to a standard format.

        Standard keys:
            id, invoice_number, series, invoice_date, seller_name,
            seller_tax_code, buyer_name, buyer_tax_code, total_amount,
            tax_amount, status, invoice_type
        """
        if not isinstance(item, dict):
            return {}

        # Map common Vietnamese field names to standard keys
        field_map = {
            # id
            "id": ["id", "Id", "ID", "maHoaDon", "soHoaDon_id"],
            # invoice_number
            "invoice_number": [
                "soHoaDon", "so_hoa_don", "invoiceNumber", "invoice_number",
                "kyHieu", "soChungTu",
            ],
            # series / ký hiệu
            "series": ["kyHieu", "ky_hieu", "series", "mauSo", "mauSoKyHieu"],
            # date
            "invoice_date": [
                "ngayHoaDon", "ngay_hoa_don", "invoiceDate", "invoice_date",
                "ngayLap", "ngayKy",
            ],
            # seller
            "seller_name": ["tenNguoiBan", "ten_nguoi_ban", "sellerName", "nccTen"],
            "seller_tax_code": ["mstNguoiBan", "mst_nguoi_ban", "sellerTaxCode", "nccMST"],
            # buyer
            "buyer_name": ["tenNguoiMua", "ten_nguoi_mua", "buyerName", "khachHangTen"],
            "buyer_tax_code": [
                "mstNguoiMua", "mst_nguoi_mua", "buyerTaxCode",
                "khachHangMST", "maSoThue",
            ],
            # amounts
            "total_amount": [
                "tongTienThanhToan", "tong_tien", "totalAmount", "total_amount",
                "tongTien", "thanhTien",
            ],
            "tax_amount": ["tienThue", "tien_thue", "taxAmount", "tax_amount"],
            # status
            "status": ["trangThai", "trang_thai", "status", "tinhTrang"],
            # type
            "invoice_type": ["loaiHoaDon", "loai_hoa_don", "invoiceType"],
        }

        result = {}
        for std_key, candidates in field_map.items():
            for candidate in candidates:
                if candidate in item and item[candidate] is not None:
                    result[std_key] = item[candidate]
                    break
            if std_key not in result:
                result[std_key] = ""

        # Ensure numeric amounts
        for amt_key in ("total_amount", "tax_amount"):
            try:
                result[amt_key] = float(str(result[amt_key]).replace(",", "").replace(".", "") or 0)
            except (ValueError, TypeError):
                result[amt_key] = 0.0

        return result

    def _parse_invoice_html(self, html_text, page, page_size):
        """
        Fallback: parse invoice list from HTML table if JSON API is unavailable.

        Returns:
            dict: {"invoices": [...], "has_more": bool, "total": int}
        """
        soup = BeautifulSoup(html_text, "html.parser")
        invoices = []

        # Check for session expiry
        if LOGIN_PATH in html_text and "dang-nhap" in html_text.lower():
            self._authenticated = False
            raise ValueError("SPV session expired (HTML redirect to login page).")

        # Find invoice table
        table = soup.find("table", class_=re.compile(r"table|invoice|hoa-don", re.I))
        if not table:
            table = soup.find("table")

        if not table:
            _logger.warning("SPV: No invoice table found in HTML response")
            return {"invoices": [], "has_more": False, "total": 0}

        rows = table.find_all("tr")
        headers = []

        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            cell_texts = [c.get_text(strip=True) for c in cells]

            # Detect header row
            if row.find("th") or any(
                kw in " ".join(cell_texts).lower()
                for kw in ["số hóa đơn", "ngày", "tổng tiền", "ký hiệu"]
            ):
                headers = cell_texts
                continue

            if not headers or len(cell_texts) < 2:
                continue

            item = {}
            for i, header in enumerate(headers):
                if i < len(cell_texts):
                    item[header] = cell_texts[i]

            invoices.append(self._normalize_invoice_item_from_html(item))

        # Try to find total count from pagination
        total = len(invoices)
        pagination = soup.find(class_=re.compile(r"pagination|pager", re.I))
        if pagination:
            total_text = pagination.get_text()
            match = re.search(r"(\d+)\s*(?:bản ghi|records|tổng)", total_text, re.I)
            if match:
                total = int(match.group(1))

        has_more = (page * page_size) < total

        _logger.info(
            "SPV: HTML parsing found %d invoices (total=%d, has_more=%s)",
            len(invoices), total, has_more,
        )

        return {"invoices": invoices, "has_more": has_more, "total": total}

    def _normalize_invoice_item_from_html(self, html_item):
        """
        Map HTML table column headers (Vietnamese) to standard invoice keys.
        """
        result = {
            "id": "",
            "invoice_number": "",
            "series": "",
            "invoice_date": "",
            "seller_name": "",
            "seller_tax_code": "",
            "buyer_name": "",
            "buyer_tax_code": "",
            "total_amount": 0.0,
            "tax_amount": 0.0,
            "status": "",
            "invoice_type": "",
        }

        for key, value in html_item.items():
            key_lower = key.lower()
            if any(k in key_lower for k in ["số hóa đơn", "so hoa don", "số hd"]):
                result["invoice_number"] = value
            elif any(k in key_lower for k in ["ký hiệu", "ky hieu", "mẫu số"]):
                result["series"] = value
            elif any(k in key_lower for k in ["ngày", "ngay"]):
                result["invoice_date"] = value
            elif any(k in key_lower for k in ["người bán", "nguoi ban", "tên ncc"]):
                result["seller_name"] = value
            elif any(k in key_lower for k in ["mst người bán", "mst ncc"]):
                result["seller_tax_code"] = value
            elif any(k in key_lower for k in ["người mua", "nguoi mua", "khách hàng"]):
                result["buyer_name"] = value
            elif any(k in key_lower for k in ["mst người mua", "mst kh", "mã số thuế"]):
                result["buyer_tax_code"] = value
            elif any(k in key_lower for k in ["tổng tiền", "tong tien", "thành tiền"]):
                try:
                    result["total_amount"] = float(
                        re.sub(r"[^\d\.]", "", value) or "0"
                    )
                except ValueError:
                    result["total_amount"] = 0.0
            elif any(k in key_lower for k in ["tiền thuế", "tien thue", "thuế"]):
                try:
                    result["tax_amount"] = float(
                        re.sub(r"[^\d\.]", "", value) or "0"
                    )
                except ValueError:
                    result["tax_amount"] = 0.0
            elif any(k in key_lower for k in ["trạng thái", "trang thai", "tình trạng"]):
                result["status"] = value

        return result
