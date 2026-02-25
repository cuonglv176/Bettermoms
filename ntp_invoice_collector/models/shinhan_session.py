# -*- coding: utf-8 -*-
"""
Shinhan Bank E-Invoice Session Manager
=======================================
Handles authentication and invoice fetching from the Shinhan Bank e-invoice
portal (https://einvoice.shinhan.com.vn).

The portal is an Angular 7 Single-Page Application (SPA) that communicates
with a backend REST API. Authentication uses JWT (JSON Web Token).

Authentication flow:
  1. GET /  → load Angular app, extract any initial CAPTCHA parameters
  2. GET /api/session/captcha  → obtain CAPTCHA image (canvas-rendered or API)
  3. POST /api/session/login   → submit {username, password, captcha} → receive JWT
  4. Use JWT in Authorization: Bearer <token> header for subsequent API calls

Invoice fetching:
  - POST /api/invoices/filter-invoice-symbol  → paginated invoice list

CAPTCHA solving:
  - Manual: caller provides the text answer
  - Auto:   uses Google Gemini Vision API to read the CAPTCHA image

This module mirrors the design of grab_session.py for consistency.
"""

import base64
import io
import json
import logging
import re
import time
from datetime import datetime, timedelta

import requests

_logger = logging.getLogger(__name__)

# ---- Constants ---------------------------------------------------------------
DEFAULT_BASE_URL = "https://einvoice.shinhan.com.vn"
LOGIN_API_PATH = "/api/session/login"
CAPTCHA_API_PATH = "/api/session/captcha"
INVOICE_LIST_API_PATH = "/api/invoices/filter-invoice-symbol"
INVOICE_DETAIL_API_PATH = "/api/invoices/detail"
INVOICE_DOWNLOAD_API_PATH = "/api/invoices/download"

SESSION_TIMEOUT_MINUTES = 30
REQUEST_TIMEOUT = 30
MAX_LOGIN_ATTEMPTS = 5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

HEADERS_BASE = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": DEFAULT_BASE_URL,
    "Referer": "%s/#/Login" % DEFAULT_BASE_URL,
}


class ShinhanEInvoiceSession:
    """
    Manages a JWT-authenticated session with the Shinhan Bank e-invoice portal.

    Usage (auto-login)::

        session = ShinhanEInvoiceSession(username="user", password="pass")
        if session.auto_login():
            result = session.fetch_invoices(date_from="2025-01-01", date_to="2025-12-31")

    Usage (manual CAPTCHA)::

        session = ShinhanEInvoiceSession(username="user", password="pass")
        captcha_b64 = session.get_captcha_image_b64()
        # ... show image to user, get answer ...
        if session.login(captcha_answer):
            result = session.fetch_invoices(...)
    """

    def __init__(self, username, password, base_url=None):
        self.username = username
        self.password = password
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

        self._session = requests.Session()
        self._session.headers.update(HEADERS_BASE)
        self._session.headers["Origin"] = self.base_url
        self._session.headers["Referer"] = "%s/#/Login" % self.base_url

        self._jwt_token = None
        self._token_expiry = None
        self._captcha_text = None      # Server-side captcha text (if provided)
        self._captcha_image_bytes = None
        self._authenticated = False
        self._auth_time = None

        self.last_error = None
        self.is_account_locked = False

    # =========================================================================
    # Public API
    # =========================================================================

    def get_captcha_image_b64(self):
        """
        Fetch the CAPTCHA image from the Shinhan portal.

        The portal renders CAPTCHA on an HTML5 canvas element. The API may
        provide the CAPTCHA as a base64-encoded image or as a URL.

        Returns:
            str: Base64-encoded PNG/JPEG image, or None on failure.
        """
        url = "%s%s" % (self.base_url, CAPTCHA_API_PATH)
        _logger.info("Shinhan: Fetching CAPTCHA from %s", url)

        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")

                # Case 1: API returns image directly
                if "image" in content_type:
                    self._captcha_image_bytes = resp.content
                    b64 = base64.b64encode(resp.content).decode("utf-8")
                    _logger.debug("Shinhan: CAPTCHA image fetched (%d bytes)", len(resp.content))
                    return b64

                # Case 2: API returns JSON with base64 image or captcha text
                try:
                    data = resp.json()
                    # Format: {"captchaImage": "base64...", "captchaText": "..."}
                    if "captchaImage" in data:
                        img_b64 = data["captchaImage"]
                        # Remove data URI prefix if present
                        if "," in img_b64:
                            img_b64 = img_b64.split(",", 1)[1]
                        self._captcha_image_bytes = base64.b64decode(img_b64)
                        # Store server-side text if provided (some portals send it)
                        self._captcha_text = data.get("captchaText", "")
                        _logger.debug("Shinhan: CAPTCHA image from JSON response")
                        return img_b64

                    # Format: {"image": "data:image/png;base64,..."}
                    if "image" in data:
                        img_data = data["image"]
                        if "," in img_data:
                            img_b64 = img_data.split(",", 1)[1]
                        else:
                            img_b64 = img_data
                        self._captcha_image_bytes = base64.b64decode(img_b64)
                        return img_b64

                    # Format: {"captchaCode": "ABCD"} — text-only CAPTCHA
                    if "captchaCode" in data:
                        self._captcha_text = data["captchaCode"]
                        _logger.info(
                            "Shinhan: Server provided captcha text directly (len=%d)",
                            len(self._captcha_text),
                        )
                        # Generate a simple image from text for display
                        return self._text_to_image_b64(self._captcha_text)

                except (ValueError, KeyError):
                    pass

                # Case 3: Raw base64 text response
                try:
                    raw = resp.text.strip()
                    if raw.startswith("data:"):
                        raw = raw.split(",", 1)[1]
                    decoded = base64.b64decode(raw)
                    self._captcha_image_bytes = decoded
                    return base64.b64encode(decoded).decode("utf-8")
                except Exception:
                    pass

            # Fallback: try to get CAPTCHA from the main page (canvas-based)
            return self._get_captcha_from_main_page()

        except requests.RequestException as e:
            self.last_error = "Failed to fetch Shinhan CAPTCHA: %s" % e
            _logger.error("Shinhan: %s", self.last_error)
            return None

    def login(self, captcha_answer):
        """
        Authenticate with the Shinhan portal API using credentials and CAPTCHA.

        Args:
            captcha_answer (str): The text answer for the current CAPTCHA.
                                  If server provided captcha text, this is ignored.

        Returns:
            bool: True if login succeeded, False otherwise.
        """
        url = "%s%s" % (self.base_url, LOGIN_API_PATH)
        _logger.info("Shinhan: Submitting login for user '%s'...", self.username)

        # Use server-provided captcha text if available
        effective_captcha = self._captcha_text or (captcha_answer.strip() if captcha_answer else "")

        payload = {
            "username": self.username,
            "password": self.password,
            "captcha": effective_captcha,
        }

        headers = {
            "Content-Type": "application/json",
        }

        try:
            resp = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            self.last_error = "Login request failed: %s" % e
            _logger.error("Shinhan: %s", self.last_error)
            return False

        # Parse response
        try:
            data = resp.json()
        except ValueError:
            self.last_error = "Login response is not valid JSON (HTTP %d)" % resp.status_code
            _logger.error("Shinhan: %s", self.last_error)
            return False

        # Check for account lock
        resp_str = json.dumps(data).lower()
        if any(kw in resp_str for kw in ["locked", "b\u1ecb kh\u00f3a", "lock", "blocked"]):
            self.is_account_locked = True
            self.last_error = "Account is locked: %s" % data
            _logger.error("Shinhan: Account '%s' is locked!", self.username)
            return False

        # Check for success — look for JWT token
        jwt_token = (
            data.get("id_token")
            or data.get("token")
            or data.get("access_token")
            or data.get("jwt")
            or data.get("accessToken")
            or data.get("idToken")
        )

        if not jwt_token and resp.status_code == 200:
            # Try nested structure
            result = data.get("result") or data.get("data") or {}
            if isinstance(result, dict):
                jwt_token = (
                    result.get("id_token")
                    or result.get("token")
                    or result.get("access_token")
                    or result.get("accessToken")
                    or result.get("idToken")
                )

        if jwt_token:
            self._jwt_token = jwt_token
            self._authenticated = True
            self._auth_time = datetime.now()

            # Parse token expiry
            self._token_expiry = self._parse_jwt_expiry(jwt_token)

            # Set Authorization header for future requests
            self._session.headers["Authorization"] = "Bearer %s" % jwt_token

            _logger.info("Shinhan: Login successful for user '%s'", self.username)
            return True

        # Login failed
        error_msg = (
            data.get("message")
            or data.get("error")
            or data.get("errorMessage")
            or data.get("msg")
            or str(data)
        )
        self.last_error = "Login failed (HTTP %d): %s" % (resp.status_code, error_msg)
        _logger.warning("Shinhan: %s", self.last_error)
        return False

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
            _logger.error("Shinhan: %s", self.last_error)
            return False

        for attempt in range(1, max_attempts + 1):
            _logger.info(
                "Shinhan: Auto-login attempt %d/%d for user '%s'",
                attempt, max_attempts, self.username,
            )

            try:
                # Reset captcha text for each attempt
                self._captcha_text = None
                captcha_b64 = self.get_captcha_image_b64()

                # If server provided captcha text directly, use it
                if self._captcha_text:
                    _logger.info(
                        "Shinhan: Using server-provided captcha text: '%s'",
                        self._captcha_text,
                    )
                    captcha_answer = self._captcha_text
                elif captcha_b64:
                    captcha_answer = self._solve_captcha_with_gemini(captcha_b64, api_key)
                    if not captcha_answer:
                        _logger.warning(
                            "Shinhan: Gemini returned empty CAPTCHA answer (attempt %d)", attempt
                        )
                        time.sleep(1)
                        continue
                    _logger.info(
                        "Shinhan: Gemini CAPTCHA answer: '%s' (attempt %d)",
                        captcha_answer, attempt,
                    )
                else:
                    _logger.warning(
                        "Shinhan: Could not fetch CAPTCHA image (attempt %d)", attempt
                    )
                    time.sleep(2)
                    continue

                if self.login(captcha_answer):
                    _logger.info(
                        "Shinhan: Auto-login succeeded on attempt %d/%d",
                        attempt, max_attempts,
                    )
                    return True

                if self.is_account_locked:
                    _logger.error("Shinhan: Account locked, stopping auto-login.")
                    return False

                _logger.warning(
                    "Shinhan: Login attempt %d failed: %s", attempt, self.last_error
                )
                time.sleep(2 * attempt)

            except Exception as e:
                _logger.warning(
                    "Shinhan: Exception on auto-login attempt %d: %s", attempt, e
                )
                self.last_error = str(e)
                time.sleep(2)

        _logger.error(
            "Shinhan: All %d auto-login attempts failed for user '%s'",
            max_attempts, self.username,
        )
        return False

    def check_session_valid(self):
        """
        Verify the current JWT token is still valid.

        Returns:
            bool: True if session is valid.
        """
        if not self._jwt_token:
            return False

        # Check expiry time
        if self._token_expiry and datetime.now() >= self._token_expiry:
            _logger.debug("Shinhan: JWT token has expired")
            return False

        # Try a lightweight API call to verify
        url = "%s/api/session/check" % self.base_url
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 401:
                self._authenticated = False
                return False
        except requests.RequestException:
            pass

        # If check endpoint doesn't exist, trust expiry time
        if self._token_expiry and datetime.now() < self._token_expiry:
            return True

        return False

    def fetch_invoices(self, date_from=None, date_to=None, page=1, page_size=50):
        """
        Fetch invoice list from the Shinhan portal API.

        Args:
            date_from (str): Start date in YYYY-MM-DD or dd/MM/yyyy format.
            date_to (str): End date in YYYY-MM-DD or dd/MM/yyyy format.
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
        if not self._authenticated or not self._jwt_token:
            raise ValueError("Not authenticated. Call login() or auto_login() first.")

        # Normalize date format to YYYY-MM-DD
        date_from_norm = self._normalize_date(date_from) if date_from else ""
        date_to_norm = self._normalize_date(date_to) if date_to else ""

        url = "%s%s" % (self.base_url, INVOICE_LIST_API_PATH)
        _logger.info(
            "Shinhan: Fetching invoices page %d (from=%s, to=%s)",
            page, date_from_norm, date_to_norm,
        )

        payload = {
            "fromDate": date_from_norm,
            "toDate": date_to_norm,
            "page": page,
            "pageSize": page_size,
            "invoiceType": "",
            "status": "",
            "keyword": "",
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % self._jwt_token,
        }

        try:
            resp = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 401:
                self._authenticated = False
                raise ValueError("Shinhan JWT token expired. Re-login required.")

            resp.raise_for_status()

            try:
                data = resp.json()
            except ValueError:
                _logger.warning("Shinhan: Invoice list response is not JSON")
                return {"invoices": [], "has_more": False, "total": 0}

            return self._normalize_invoice_response(data, page, page_size)

        except ValueError:
            raise
        except requests.RequestException as e:
            _logger.error("Shinhan: Invoice fetch error (page %d): %s", page, e)
            raise

    def get_jwt_token(self):
        """Return the current JWT token string."""
        return self._jwt_token

    def get_token_expiry(self):
        """Return the token expiry datetime, or None."""
        return self._token_expiry

    def restore_jwt(self, jwt_token):
        """
        Restore a previously saved JWT token.

        Args:
            jwt_token (str): JWT token string.
        """
        if not jwt_token:
            return
        self._jwt_token = jwt_token
        self._token_expiry = self._parse_jwt_expiry(jwt_token)
        self._session.headers["Authorization"] = "Bearer %s" % jwt_token
        self._authenticated = True
        self._auth_time = datetime.now()
        _logger.debug("Shinhan: JWT token restored (expires=%s)", self._token_expiry)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _get_captcha_from_main_page(self):
        """
        Fallback: load the main Angular app page and try to extract CAPTCHA
        parameters from the page source or initial API calls.

        Returns:
            str: Base64-encoded image, or None.
        """
        url = self.base_url
        _logger.debug("Shinhan: Trying to get CAPTCHA from main page: %s", url)

        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            # Look for CAPTCHA API endpoint in page source
            captcha_patterns = [
                r'captcha["\s]*:["\s]*"([^"]+)"',
                r'captchaUrl["\s]*:["\s]*"([^"]+)"',
                r'/api/[^"]*captcha[^"]*',
            ]

            for pattern in captcha_patterns:
                match = re.search(pattern, resp.text, re.I)
                if match:
                    captcha_url = match.group(1)
                    if not captcha_url.startswith("http"):
                        captcha_url = "%s%s" % (self.base_url, captcha_url)
                    _logger.debug("Shinhan: Found captcha URL in page: %s", captcha_url)
                    try:
                        img_resp = self._session.get(captcha_url, timeout=REQUEST_TIMEOUT)
                        if img_resp.status_code == 200:
                            self._captcha_image_bytes = img_resp.content
                            return base64.b64encode(img_resp.content).decode("utf-8")
                    except Exception:
                        pass

        except requests.RequestException as e:
            _logger.warning("Shinhan: Could not load main page for CAPTCHA: %s", e)

        return None

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
                "This is a CAPTCHA image from a Vietnamese bank e-invoice portal (Shinhan Bank). "
                "Please read the text or numbers shown in the image carefully. "
                "Return ONLY the exact characters you see, with no spaces, "
                "no punctuation, no explanation. "
                "The CAPTCHA typically contains 4-6 alphanumeric characters. "
                "Be precise — wrong answers will lock the account."
            )

            response = model.generate_content([prompt, image])
            answer = response.text.strip()
            # Clean: remove spaces and common noise characters
            answer = re.sub(r"[\s\.\,\!\?\-\_]", "", answer)
            _logger.debug("Shinhan: Gemini CAPTCHA response: '%s'", answer)
            return answer

        except ImportError:
            _logger.warning(
                "Shinhan: google-generativeai or Pillow not installed. "
                "Run: pip install google-generativeai pillow"
            )
            return ""
        except Exception as e:
            _logger.warning("Shinhan: Gemini CAPTCHA solving failed: %s", e)
            return ""

    def _solve_captcha_with_openai(self, captcha_b64, api_key):
        """Deprecated: Use _solve_captcha_with_gemini() instead."""
        return self._solve_captcha_with_gemini(captcha_b64, api_key)

    def _parse_jwt_expiry(self, jwt_token):
        """
        Parse the expiry time from a JWT token payload.

        Args:
            jwt_token (str): JWT token string.

        Returns:
            datetime: Token expiry time, or None if unparseable.
        """
        try:
            # JWT format: header.payload.signature (base64url encoded)
            parts = jwt_token.split(".")
            if len(parts) < 2:
                return None

            # Decode payload (add padding if needed)
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(int(exp))
        except Exception as e:
            _logger.debug("Shinhan: Could not parse JWT expiry: %s", e)

        # Default: 30 minutes from now
        return datetime.now() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    def _normalize_date(self, date_str):
        """
        Normalize date string to YYYY-MM-DD format.

        Accepts: dd/MM/yyyy, yyyy-MM-dd, dd-MM-yyyy
        """
        if not date_str:
            return ""
        date_str = str(date_str).strip()

        # Already ISO format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

        # Vietnamese format: dd/MM/yyyy
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", date_str)
        if m:
            return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))

        # dd-MM-yyyy
        m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", date_str)
        if m:
            return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))

        return date_str

    def _normalize_invoice_response(self, data, page, page_size):
        """
        Normalize various JSON response formats into a standard dict.

        Returns:
            dict: {"invoices": [...], "has_more": bool, "total": int}
        """
        invoices = []
        total = 0

        # Format 1: {"data": [...], "total": N, "page": N}
        if isinstance(data, dict) and "data" in data:
            raw_list = data.get("data", [])
            total = int(data.get("total", data.get("totalCount", len(raw_list))))
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 2: {"items": [...], "totalCount": N}
        elif isinstance(data, dict) and "items" in data:
            raw_list = data.get("items", [])
            total = int(data.get("totalCount", data.get("total", len(raw_list))))
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 3: {"invoices": [...], "total": N}
        elif isinstance(data, dict) and "invoices" in data:
            raw_list = data.get("invoices", [])
            total = int(data.get("total", len(raw_list)))
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

        # Format 4: {"result": {...}}
        elif isinstance(data, dict) and "result" in data:
            return self._normalize_invoice_response(data["result"], page, page_size)

        # Format 5: direct list
        elif isinstance(data, list):
            raw_list = data
            total = len(raw_list)
            invoices = [self._normalize_invoice_item(item) for item in raw_list]

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

        field_map = {
            "id": ["id", "Id", "ID", "invoiceId", "invoice_id"],
            "invoice_number": [
                "invoiceNo", "invoice_no", "invoiceNumber", "invoice_number",
                "soHoaDon", "so_hoa_don",
            ],
            "series": [
                "invoiceSymbol", "invoice_symbol", "series", "kyHieu",
                "mauSo", "mauSoKyHieu",
            ],
            "invoice_date": [
                "invoiceDate", "invoice_date", "issuedDate", "issued_date",
                "ngayHoaDon", "ngayLap",
            ],
            "seller_name": [
                "sellerName", "seller_name", "tenNguoiBan", "companyName",
            ],
            "seller_tax_code": [
                "sellerTaxCode", "seller_tax_code", "mstNguoiBan", "taxCode",
            ],
            "buyer_name": [
                "buyerName", "buyer_name", "tenNguoiMua", "customerName",
            ],
            "buyer_tax_code": [
                "buyerTaxCode", "buyer_tax_code", "mstNguoiMua",
                "customerTaxCode", "maSoThue",
            ],
            "total_amount": [
                "totalAmount", "total_amount", "tongTien", "amount",
                "totalPayment", "tongTienThanhToan",
            ],
            "tax_amount": [
                "taxAmount", "tax_amount", "tienThue", "vatAmount",
            ],
            "status": [
                "status", "invoiceStatus", "trangThai", "tinhTrang",
            ],
            "invoice_type": [
                "invoiceType", "invoice_type", "loaiHoaDon", "type",
            ],
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
                val = str(result[amt_key]).replace(",", "").replace(".", "")
                # Handle Vietnamese number format (dots as thousand separators)
                # Try to detect: if original has dot but no comma, it might be decimal
                orig = str(result[amt_key])
                if re.match(r"^\d{1,3}(\.\d{3})+$", orig):
                    # Thousand-separated: 1.234.567 → 1234567
                    val = orig.replace(".", "")
                elif re.match(r"^\d+\.\d{1,2}$", orig):
                    # Decimal: 1234.56
                    val = orig.replace(",", "")
                result[amt_key] = float(val or 0)
            except (ValueError, TypeError):
                result[amt_key] = 0.0

        return result

    def _text_to_image_b64(self, text):
        """
        Generate a simple PNG image from text (for display when server provides text CAPTCHA).

        Args:
            text (str): CAPTCHA text.

        Returns:
            str: Base64-encoded PNG image.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (120, 40), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), text, fill=(0, 0, 0))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except ImportError:
            # Pillow not available — return a minimal 1x1 PNG
            _logger.debug("Shinhan: Pillow not available for text-to-image conversion")
            minimal_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
                b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
                b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            return base64.b64encode(minimal_png).decode("utf-8")
