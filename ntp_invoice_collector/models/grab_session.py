# -*- coding: utf-8 -*-
"""
Grab E-Invoice Portal Session Manager
========================================
Manages authentication and data retrieval from the HILO-based
Grab e-invoice portal at vn.einvoice.grab.com.

Authentication flow:
  1. GET /tai-khoan/dang-nhap  → obtain CSRF token + session cookie
  2. GET /Captcha/CaptchaImage → fetch CAPTCHA image (PNG)
  3. (Optional) Solve CAPTCHA via Google Gemini Vision API
  4. POST /tai-khoan/dang-nhap → submit form (username, password, captcha)
  5. On success, .ASPXAUTH cookie is set → session is authenticated

Invoice retrieval:
  - Strategy 1: POST /Invoice/DowloadReportData → Excel/CSV report (all data)
  - Strategy 2: GET  /hoa-don/danh-sach        → HTML table parsing (paginated)
  - Download:   POST /Invoice/DowloadData       → ZIP of PDF/XML files

This module is a pure Python library (no Odoo dependencies) so it can be
tested independently.
"""

import base64
import csv
import io
import logging
import os
import re
import time
from datetime import datetime, timedelta

import requests

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portal URL paths
# ---------------------------------------------------------------------------
LOGIN_PATH = "/tai-khoan/dang-nhap"
LOGOUT_PATH = "/tai-khoan/dang-xuat"
CAPTCHA_PATH = "/Captcha/CaptchaImage"
INVOICE_LIST_PATH = "/hoa-don/danh-sach"
INVOICE_DOWNLOAD_PATH = "/Invoice/DowloadData"
INVOICE_REPORT_PATH = "/Invoice/DowloadReportData"

# ---------------------------------------------------------------------------
# Timeouts & limits
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 120
MAX_AUTO_LOGIN_ATTEMPTS = 5  # increased from 3 → 5 for better CAPTCHA success rate

# ---------------------------------------------------------------------------
# Browser-like headers
# ---------------------------------------------------------------------------
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


class GrabEInvoiceSession:
    """
    Manages a single authenticated session with the Grab e-invoice portal.

    Usage (auto-login)::

        session = GrabEInvoiceSession("user", "pass")
        if session.auto_login(gemini_api_key="AIza..."):
            result = session.fetch_invoices("01/01/2025", "31/01/2025")
            for inv in result["invoices"]:
                print(inv)

    Usage (manual CAPTCHA)::

        session = GrabEInvoiceSession("user", "pass")
        session.prepare_login()
        captcha_bytes = session.get_captcha_image()
        # ... show captcha_bytes to user, get answer ...
        if session.login("AB12"):
            result = session.fetch_invoices()
    """

    def __init__(self, username, password, base_url=None):
        self.username = username
        self.password = password
        self.base_url = (base_url or "https://vn.einvoice.grab.com").rstrip("/")

        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

        self._csrf_token = None
        self._captcha_url = None   # extracted from login page HTML at runtime
        self._authenticated = False
        self._auth_time = None
        self._last_error = ""
        self._account_locked = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path):
        return "%s%s" % (self.base_url, path)

    @property
    def last_error(self):
        return self._last_error

    @property
    def is_account_locked(self):
        return self._account_locked

    # ------------------------------------------------------------------
    # Strategy 1: Auto-Login (CAPTCHA solved by AI)
    # ------------------------------------------------------------------

    def auto_login(self, captcha_api_key=None, gemini_api_key=None, openai_api_key=None, max_attempts=None):
        """
        Fully automated login: load page → fetch CAPTCHA → solve via 2captcha.com → submit.
        Args:
            captcha_api_key (str): 2captcha.com API key. Falls back to CAPTCHA_API_KEY env var.
            gemini_api_key (str): Deprecated. Use captcha_api_key instead.
            openai_api_key (str): Deprecated. Use captcha_api_key instead.
            max_attempts (int): Maximum number of CAPTCHA-solve-and-login attempts.
        Returns:
            bool: True if login succeeded.
        """
        if max_attempts is None:
            max_attempts = MAX_AUTO_LOGIN_ATTEMPTS
        api_key = (
            captcha_api_key
            or gemini_api_key
            or openai_api_key
            or os.environ.get("CAPTCHA_API_KEY", "")
            or os.environ.get("TWOCAPTCHA_API_KEY", "")
        )
        if not api_key:
            self._last_error = (
                "No 2captcha.com API key provided for auto-CAPTCHA solving. "
                "Set CAPTCHA_API_KEY environment variable or provide it in Collector Config."
            )
            _logger.error(self._last_error)
            return False

        _logger.info(
            "Starting auto-login for user: %s (max %d attempts)",
            self.username, max_attempts,
        )

        for attempt in range(1, max_attempts + 1):
            try:
                # Step 1: Load login page (fresh session each attempt)
                if not self.prepare_login():
                    _logger.warning(
                        "Attempt %d: Failed to prepare login page", attempt,
                    )
                    continue

                # Brief pause to let the server register the session before
                # requesting the CAPTCHA — portals often return HTML if the
                # CAPTCHA is requested too quickly after the login page load.
                time.sleep(1.0 + attempt * 0.5)

                # Step 2: Fetch CAPTCHA image
                captcha_bytes = self.get_captcha_image()
                if not captcha_bytes:
                    _logger.warning(
                        "Attempt %d: Failed to fetch CAPTCHA image. "
                        "Last error: %s",
                        attempt, self._last_error,
                    )
                    continue

                # Step 3: Solve CAPTCHA via 2captcha.com
                captcha_answer = self._solve_captcha_with_2captcha(
                    captcha_bytes, api_key,
                )
                if not captcha_answer:
                    _logger.warning(
                        "Attempt %d: CAPTCHA solving returned empty", attempt,
                    )
                    continue

                _logger.info(
                    "Attempt %d: CAPTCHA solved as '%s'", attempt, captcha_answer,
                )

                # Step 4: Submit login
                login_result = self.login(captcha_answer)
                if login_result:
                    _logger.info(
                        "Auto-login successful on attempt %d for user: %s",
                        attempt, self.username,
                    )
                    return True

                # Check if account is locked — no point retrying
                if self._account_locked:
                    _logger.error(
                        "Account is LOCKED. Stopping auto-login. Error: %s",
                        self._last_error,
                    )
                    return False

                _logger.warning(
                    "Login attempt %d failed: %s", attempt, self._last_error,
                )

            except Exception as e:
                self._last_error = "Login error (attempt %d): %s" % (attempt, str(e))
                _logger.error(self._last_error, exc_info=True)

            # Wait before retry (increasing delay)
            if attempt < max_attempts:
                delay = 2 * attempt
                _logger.info("Waiting %ds before retry...", delay)
                time.sleep(delay)

        self._last_error = (
            "Auto-login failed after %d attempts for user: %s. Last error: %s"
            % (max_attempts, self.username, self._last_error or "Unknown")
        )
        _logger.error(self._last_error)
        return False

    def _solve_captcha_with_2captcha(self, image_bytes, api_key):
        """
        Solve image CAPTCHA using 2captcha.com paid service.
        Uses only the built-in `requests` library — no extra SDK needed.

        Flow:
          1. POST image to 2captcha /in.php  → get task ID
          2. Poll 2captcha /res.php every 5s → get answer text

        Args:
            image_bytes (bytes): Raw PNG/JPEG image data.
            api_key (str): 2captcha.com API key.

        Returns:
            str: The CAPTCHA text, or empty string on failure.
        """
        try:
            import base64 as _b64
            import time as _time

            img_b64 = _b64.b64encode(image_bytes).decode("utf-8")

            # Step 1: Submit CAPTCHA image
            submit_resp = requests.post(
                "https://2captcha.com/in.php",
                data={
                    "key": api_key,
                    "method": "base64",
                    "body": img_b64,
                    "json": 1,
                },
                timeout=30,
            )
            submit_data = submit_resp.json()
            if submit_data.get("status") != 1:
                _logger.warning(
                    "Grab: 2captcha submit failed: %s", submit_data.get("request")
                )
                return ""

            task_id = submit_data["request"]
            _logger.info("Grab: 2captcha task submitted, id=%s", task_id)

            # Step 2: Poll for result (max 60s)
            for _ in range(12):
                _time.sleep(5)
                result_resp = requests.get(
                    "https://2captcha.com/res.php",
                    params={"key": api_key, "action": "get", "id": task_id, "json": 1},
                    timeout=30,
                )
                result_data = result_resp.json()
                if result_data.get("status") == 1:
                    answer = result_data["request"].strip()
                    answer = re.sub(r"[^A-Za-z0-9]", "", answer)
                    _logger.info("Grab: 2captcha answer: '%s'", answer)
                    return answer
                if result_data.get("request") != "CAPCHA_NOT_READY":
                    _logger.warning(
                        "Grab: 2captcha error: %s", result_data.get("request")
                    )
                    return ""

            _logger.warning("Grab: 2captcha timed out waiting for answer")
            return ""

        except Exception as e:
            _logger.error("Grab: 2captcha CAPTCHA solving error: %s", e)
            return ""

    def _solve_captcha_with_gemini(self, image_bytes, api_key):
        """Deprecated: Use _solve_captcha_with_2captcha() instead."""
        return self._solve_captcha_with_2captcha(image_bytes, api_key)

    def _solve_captcha_with_openai(self, image_bytes, api_key):
        """Deprecated: Use _solve_captcha_with_2captcha() instead."""
        return self._solve_captcha_with_2captcha(image_bytes, api_key)

    # ------------------------------------------------------------------
    # Strategy 2: Cookie Restore
    # ------------------------------------------------------------------

    def restore_cookies(self, cookie_dict):
        """Restore session from a previously saved cookie dictionary."""
        if not cookie_dict:
            return
        for name, value in cookie_dict.items():
            self._session.cookies.set(name, value)
        if ".ASPXAUTH" in cookie_dict:
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info("Session restored from stored cookies")

    def restore_aspx_cookie(self, aspx_auth_value):
        """Restore session from just the .ASPXAUTH cookie value."""
        if aspx_auth_value:
            self._session.cookies.set(".ASPXAUTH", aspx_auth_value)
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info("Session restored from .ASPXAUTH cookie")

    # ------------------------------------------------------------------
    # Strategy 3: Manual Login (2-step)
    # ------------------------------------------------------------------

    def prepare_login(self):
        """
        Step 1: Load the login page to obtain CSRF token and session cookie.

        Returns:
            bool: True if preparation succeeded.
        """
        _logger.info("Preparing Grab e-invoice login session...")
        try:
            response = self._session.get(
                self._url(LOGIN_PATH),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self._last_error = "Failed to load login page: %s" % str(e)
            _logger.error(self._last_error)
            return False

        # Extract CSRF token from hidden input
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

            # Extract the actual CAPTCHA image URL from the login page HTML.
            # Do NOT rely on the hardcoded CAPTCHA_PATH — the portal may use
            # a session-scoped token in the URL (e.g. /Captcha/CaptchaImage?id=xxx).
            captcha_match = re.search(
                r'<img[^>]+src=["\']([^"\']*[Cc]aptcha[^"\']*)["\']',
                response.text,
            )
            if captcha_match:
                src = captcha_match.group(1)
                # Make absolute URL
                if not src.startswith("http"):
                    src = src if src.startswith("/") else "/" + src
                    src = self._url(src)
                # Strip any existing query string — we'll add cache-bust later
                self._captcha_url = src.split("?")[0]
                _logger.info("CAPTCHA URL extracted from login page: %s", self._captcha_url)
            else:
                # Fallback to hardcoded path (kept for backward compat)
                self._captcha_url = self._url(CAPTCHA_PATH)
                _logger.warning(
                    "No CAPTCHA <img> found in login page HTML — "
                    "falling back to hardcoded path: %s. "
                    "Login page preview: %s",
                    self._captcha_url,
                    response.text[:800],
                )

            return True

        self._last_error = "Could not extract CSRF token from login page"
        _logger.warning(self._last_error)
        return False

    def get_captcha_image(self):
        """
        Step 2: Fetch the CAPTCHA image. Must call prepare_login() first.

        Returns:
            bytes: Raw PNG image bytes, or None on failure.
        """
        # Use the URL extracted from the login page HTML (preferred),
        # or fall back to the hardcoded path if prepare_login() wasn't called.
        captcha_url = self._captcha_url or self._url(CAPTCHA_PATH)
        _logger.info("Fetching CAPTCHA image from: %s", captcha_url)
        try:
            response = self._session.get(
                captcha_url,
                params={"t": int(time.time() * 1000)},  # cache-bust: prevents 304/cached HTML
                timeout=REQUEST_TIMEOUT,
                headers={
                    "Referer": self._url(LOGIN_PATH),
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Fetch-Dest": "image",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "same-origin",
                },
            )
        except requests.RequestException as e:
            self._last_error = "Failed to fetch CAPTCHA: %s" % str(e)
            _logger.error(self._last_error)
            return None

        content_type = response.headers.get("content-type", "")

        if response.status_code == 200:
            # Check content-type
            if content_type.startswith("image/"):
                _logger.info(
                    "CAPTCHA image fetched: %d bytes, type: %s",
                    len(response.content), content_type,
                )
                return response.content

            # Check PNG magic bytes: \x89PNG
            if response.content[:4] == b'\x89PNG':
                _logger.info(
                    "CAPTCHA image fetched (PNG magic): %d bytes",
                    len(response.content),
                )
                return response.content

            # Check JPEG magic bytes: \xff\xd8\xff
            if response.content[:3] == b'\xff\xd8\xff':
                _logger.info(
                    "CAPTCHA image fetched (JPEG magic): %d bytes",
                    len(response.content),
                )
                return response.content

            # HTML response — portal likely blocked the request or session issue
            if "text/html" in content_type and len(response.content) > 1000:
                _logger.warning(
                    "CAPTCHA endpoint returned HTML (%d bytes, URL: %s). "
                    "Portal may be blocking automation. HTML preview: %s",
                    len(response.content),
                    response.url,
                    response.text[:500],
                )

                # Strategy A: extract embedded base64 image from HTML
                img_match = re.search(
                    r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)',
                    response.text,
                )
                if img_match:
                    try:
                        img_data = base64.b64decode(img_match.group(1))
                        _logger.info("Extracted embedded CAPTCHA from HTML: %d bytes", len(img_data))
                        return img_data
                    except Exception:
                        pass

                # Strategy B: look for a different <img> src pointing to CAPTCHA
                src_match = re.search(
                    r'<img[^>]+src="([^"]*[Cc]aptcha[^"]*)"',
                    response.text,
                )
                if src_match:
                    alt_path = src_match.group(1)
                    _logger.info("Found alternative CAPTCHA src in HTML: %s", alt_path)
                    if not alt_path.startswith("http"):
                        alt_path = self._url(alt_path if alt_path.startswith("/") else "/" + alt_path)
                    try:
                        alt_resp = self._session.get(
                            alt_path,
                            params={"t": int(time.time() * 1000)},
                            timeout=REQUEST_TIMEOUT,
                            headers={"Referer": self._url(LOGIN_PATH)},
                        )
                        if alt_resp.content[:4] in (b'\x89PNG', b'\xff\xd8'):
                            _logger.info("Got CAPTCHA from alternative URL: %d bytes", len(alt_resp.content))
                            return alt_resp.content
                    except Exception as e:
                        _logger.warning("Alternative CAPTCHA fetch failed: %s", e)

                self._last_error = "CAPTCHA endpoint returned HTML instead of image"
                return None

            # Small response that might still be an image
            if len(response.content) > 200:
                _logger.info(
                    "CAPTCHA response: %d bytes, type: %s — treating as image",
                    len(response.content), content_type,
                )
                return response.content

        self._last_error = (
            "Unexpected CAPTCHA response: HTTP %d, type: %s, size: %d"
            % (response.status_code, content_type, len(response.content))
        )
        _logger.warning(self._last_error)
        return None

    def get_captcha_image_b64(self):
        """Fetch CAPTCHA image and return as base64 string for Odoo Binary field."""
        raw = self.get_captcha_image()
        if raw:
            return base64.b64encode(raw).decode("utf-8")
        return ""

    def login(self, captcha_answer):
        """
        Step 3: Submit login form with CAPTCHA answer.

        Args:
            captcha_answer (str): The CAPTCHA text (4 characters).

        Returns:
            bool: True if login was successful.
        """
        if not self._csrf_token:
            self._last_error = "CSRF token not available. Call prepare_login() first."
            raise ValueError(self._last_error)

        _logger.info(
            "Attempting Grab login for user: %s (captcha: %s)",
            self.username, captcha_answer,
        )

        payload = {
            "__RequestVerificationToken": self._csrf_token,
            "UserName": self.username,
            "Password": self.password,
            "captch": captcha_answer,  # NOTE: field name is "captch" (not "captcha")
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
        except requests.RequestException as e:
            self._last_error = "Login request failed: %s" % str(e)
            _logger.error(self._last_error)
            return False

        final_url = response.url
        response_text = response.text

        _logger.info(
            "Login POST result: HTTP %d, final URL: %s, body size: %d",
            response.status_code, final_url, len(response_text),
        )

        # ------------------------------------------------------------------
        # Check for specific error messages
        # ------------------------------------------------------------------
        error_patterns = {
            "bị khóa": "Account is LOCKED — contact Grab support to unlock",
            "quá số lần": "Too many failed attempts — account LOCKED",
            "locked": "Account is LOCKED",
            "Tài khoản hoặc mật khẩu không đúng": "Wrong username or password",
            "Mã kiểm tra không đúng": "Wrong CAPTCHA code",
            "Mã kiểm tra không hợp lệ": "Invalid CAPTCHA code",
            "Invalid captcha": "Invalid CAPTCHA",
            "Invalid username or password": "Wrong credentials",
        }

        for pattern, msg in error_patterns.items():
            if pattern.lower() in response_text.lower():
                self._last_error = "Login failed: %s" % msg
                _logger.warning(self._last_error)

                # Detect account locked
                if any(kw in pattern.lower() for kw in ["khóa", "locked", "quá số lần"]):
                    self._account_locked = True
                    _logger.error("ACCOUNT LOCKED detected for user: %s", self.username)

                return False

        # ------------------------------------------------------------------
        # Success indicators
        # ------------------------------------------------------------------
        # 1. .ASPXAUTH cookie is set
        aspx_cookie = self._session.cookies.get(".ASPXAUTH")
        if aspx_cookie:
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info(
                "Login successful! .ASPXAUTH cookie obtained. Final URL: %s",
                final_url,
            )
            return True

        # 2. Redirected away from login page
        if "dang-nhap" not in final_url.lower() and response.status_code == 200:
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info(
                "Login appears successful (redirected to: %s)", final_url,
            )
            return True

        # 3. No login form in response
        if "UserName" not in response_text and "Đăng nhập" not in response_text:
            self._authenticated = True
            self._auth_time = datetime.now()
            _logger.info("Login appears successful (no login form in response)")
            return True

        self._last_error = (
            "Login failed: no .ASPXAUTH cookie and still on login page. "
            "This usually means wrong CAPTCHA. Final URL: %s" % final_url
        )
        _logger.warning(self._last_error)
        return False

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def is_authenticated(self):
        """Check if the session appears to be authenticated."""
        if not self._authenticated or not self._auth_time:
            return False
        elapsed = datetime.now() - self._auth_time
        if elapsed > timedelta(minutes=25):
            _logger.info("Session may have expired (age: %s)", elapsed)
            return False
        return True

    def check_session_valid(self):
        """
        Actively verify if the session is still valid by making a test request.

        Returns:
            bool: True if session is still valid.
        """
        try:
            response = self._session.get(
                self._url(INVOICE_LIST_PATH),
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )

            # 302 redirect to login = session expired
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                if "SignOut" in location or "dang-nhap" in location.lower():
                    _logger.info("Session expired (redirected to: %s)", location)
                    self._authenticated = False
                    return False

            # 200 = check if it's actually the invoice page
            if response.status_code == 200:
                if "Đăng nhập" in response.text and "UserName" in response.text:
                    _logger.info("Session expired (login form shown)")
                    self._authenticated = False
                    return False
                self._authenticated = True
                self._auth_time = datetime.now()
                return True

        except Exception as e:
            _logger.warning("Session check failed: %s", e)

        self._authenticated = False
        return False

    def get_all_cookies(self):
        """Export all session cookies as a dictionary for persistence."""
        return {c.name: c.value for c in self._session.cookies}

    def get_aspx_cookie(self):
        """Get the .ASPXAUTH cookie value for persistence."""
        return self._session.cookies.get(".ASPXAUTH", "")

    # ------------------------------------------------------------------
    # Invoice Fetching
    # ------------------------------------------------------------------

    def fetch_invoices(self, date_from=None, date_to=None, page=1, page_size=50):
        """
        Fetch the invoice list from the portal.

        Strategy:
          1. First try to download Excel report via /Invoice/DowloadReportData
          2. Fallback to HTML table parsing from /hoa-don/danh-sach

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

        # Strategy 1: Try Excel report download (only on first page)
        if page == 1:
            try:
                excel_result = self._fetch_invoices_via_report(date_from, date_to)
                if excel_result and excel_result.get("invoices"):
                    _logger.info(
                        "Successfully fetched %d invoices via Excel report",
                        len(excel_result["invoices"]),
                    )
                    return excel_result
            except Exception as e:
                _logger.info(
                    "Excel report download failed, falling back to HTML: %s", e,
                )

        # Strategy 2: HTML table parsing
        return self._fetch_invoices_via_html(date_from, date_to, page, page_size)

    def _fetch_invoices_via_report(self, date_from, date_to):
        """Fetch invoices by downloading the Excel report from the portal."""
        _logger.info("Attempting to download Excel report: %s to %s", date_from, date_to)

        # Visit the invoice list page first (may set required tokens)
        try:
            list_resp = self._session.get(
                self._url(INVOICE_LIST_PATH),
                params={"dateFrom": date_from, "dateTo": date_to},
                timeout=REQUEST_TIMEOUT,
                headers={"Referer": self._url(INVOICE_LIST_PATH)},
            )
            if "dang-nhap" in list_resp.url.lower() or "SignOut" in list_resp.url:
                self._authenticated = False
                raise ValueError("Session expired during report download")
        except requests.RequestException as e:
            _logger.warning("Failed to load invoice list page: %s", e)
            raise

        # Download the report
        try:
            payload = {"dateFrom": date_from, "dateTo": date_to}
            response = self._session.post(
                self._url(INVOICE_REPORT_PATH),
                data=payload,
                timeout=DOWNLOAD_TIMEOUT,
                headers={
                    "Referer": self._url(INVOICE_LIST_PATH),
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                },
            )

            _logger.info(
                "Report download: HTTP %d, type: %s, size: %d",
                response.status_code,
                response.headers.get("content-type", ""),
                len(response.content),
            )

            if response.status_code != 200 or len(response.content) < 100:
                return None

            content_type = response.headers.get("content-type", "")

            # Try to parse as Excel
            if ("spreadsheet" in content_type
                    or "excel" in content_type
                    or "octet-stream" in content_type
                    or response.content[:4] == b'PK\x03\x04'     # ZIP/XLSX magic
                    or response.content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'  # XLS
            ):
                return self._parse_excel_report(response.content)

            # Try CSV/text
            if "text/" in content_type:
                return self._parse_csv_report(response.text)

            # Try JSON
            if "json" in content_type:
                try:
                    data = response.json()
                    return self._parse_invoice_list_json(data)
                except Exception:
                    pass

            _logger.info("Report response not a recognized format (type: %s)", content_type)
            return None

        except requests.RequestException as e:
            _logger.warning("Report download request failed: %s", e)
            raise

    def _parse_excel_report(self, content):
        """Parse Excel report content into invoice list."""
        invoices = []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(
                io.BytesIO(content), read_only=True, data_only=True,
            )
            ws = wb.active
            if not ws:
                return None

            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return None

            # Find header row
            header_row_idx = None
            headers = []
            for idx, row in enumerate(rows):
                row_text = " ".join(str(c or "").lower() for c in row)
                if any(kw in row_text for kw in [
                    "ký hiệu", "số hóa đơn", "invoice", "hóa đơn",
                    "ngày", "tổng tiền", "total",
                ]):
                    header_row_idx = idx
                    headers = [str(c or "").strip().lower() for c in row]
                    break

            if header_row_idx is None:
                header_row_idx = 0
                headers = [str(c or "").strip().lower() for c in rows[0]]

            _logger.info("Excel headers (row %d): %s", header_row_idx, headers)

            col_map = self._detect_column_map(headers)
            _logger.info("Excel column mapping: %s", col_map)

            for row in rows[header_row_idx + 1:]:
                cells = [str(c or "").strip() for c in row]
                if not any(cells):
                    continue
                invoice = self._extract_invoice_from_cells(cells, col_map, "")
                if invoice:
                    invoices.append(invoice)

            wb.close()
            _logger.info("Parsed %d invoices from Excel report", len(invoices))

        except ImportError:
            _logger.warning("openpyxl not installed, cannot parse Excel")
            return None
        except Exception as e:
            _logger.error("Error parsing Excel report: %s", e, exc_info=True)
            return None

        return {"invoices": invoices, "total": len(invoices), "has_more": False}

    def _parse_csv_report(self, text):
        """Parse CSV/text report into invoice list."""
        invoices = []
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return None

            headers = [h.strip().lower() for h in rows[0]]
            col_map = self._detect_column_map(headers)

            for row in rows[1:]:
                cells = [c.strip() for c in row]
                if not any(cells):
                    continue
                invoice = self._extract_invoice_from_cells(cells, col_map, "")
                if invoice:
                    invoices.append(invoice)

            _logger.info("Parsed %d invoices from CSV report", len(invoices))
        except Exception as e:
            _logger.error("Error parsing CSV report: %s", e)
            return None

        return {"invoices": invoices, "total": len(invoices), "has_more": False}

    def _fetch_invoices_via_html(self, date_from, date_to, page, page_size):
        """Fetch invoices by parsing the HTML table from the invoice list page."""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "page": page,
            "pageSize": page_size,
        }

        try:
            response = self._session.get(
                self._url(INVOICE_LIST_PATH),
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={"Referer": self._url(INVOICE_LIST_PATH)},
            )
        except requests.RequestException as e:
            _logger.error("Invoice list request failed: %s", e)
            raise

        _logger.info(
            "Invoice list response: HTTP %d, URL: %s, size: %d bytes",
            response.status_code, response.url[:100], len(response.text),
        )

        # Check if redirected to login (session expired)
        if "dang-nhap" in response.url.lower() or "SignOut" in response.url:
            self._authenticated = False
            raise ValueError("Session expired: redirected to %s" % response.url)

        # Check if response contains login form
        if (
            "UserName" in response.text
            and "Password" in response.text
            and "captch" in response.text
        ):
            self._authenticated = False
            raise ValueError("Session expired: login form returned instead of invoice list")

        content_type = response.headers.get("content-type", "")

        # Try JSON first
        if "application/json" in content_type:
            try:
                data = response.json()
                return self._parse_invoice_list_json(data)
            except Exception:
                pass

        # Parse HTML table
        return self._parse_invoice_list_html(response.text, page, page_size)

    def _parse_invoice_list_html(self, html, page, page_size):
        """Parse HTML table from the invoice list page."""
        invoices = []

        try:
            # Find the main data table
            table_match = re.search(
                r'<table[^>]*class="[^"]*table[^"]*"[^>]*>(.*?)</table>',
                html, re.DOTALL | re.IGNORECASE,
            )
            if not table_match:
                table_match = re.search(
                    r'<table[^>]*>(.*?)</table>',
                    html, re.DOTALL | re.IGNORECASE,
                )

            if not table_match:
                _logger.warning(
                    "No table found in invoice list HTML (size: %d)", len(html),
                )
                _logger.debug("HTML preview: %s", html[:3000])
                return {"invoices": [], "total": 0, "has_more": False}

            table_html = table_match.group(1)

            # Extract header columns
            header_cells = re.findall(
                r'<th[^>]*>(.*?)</th>', table_html, re.DOTALL | re.IGNORECASE,
            )
            tag_strip = re.compile(r'<[^>]+>')
            headers = [tag_strip.sub("", h).strip().lower() for h in header_cells]
            _logger.info("Table headers found: %s", headers)

            col_map = self._detect_column_map(headers)
            _logger.info("Column mapping: %s", col_map)

            # Parse data rows from <tbody>
            tbody_match = re.search(
                r'<tbody[^>]*>(.*?)</tbody>',
                table_html, re.DOTALL | re.IGNORECASE,
            )
            search_html = tbody_match.group(1) if tbody_match else table_html

            row_pattern = re.compile(
                r'<tr[^>]*?(?:id="([^"]*)")?[^>]*>(.*?)</tr>',
                re.DOTALL | re.IGNORECASE,
            )
            td_pattern = re.compile(
                r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE,
            )

            for row_match in row_pattern.finditer(search_html):
                row_id = row_match.group(1) or ""
                row_html = row_match.group(2)

                tds = td_pattern.findall(row_html)
                if len(tds) < 3:
                    continue

                cells = [tag_strip.sub("", td).strip() for td in tds]

                # Skip header-like rows
                cells_text = " ".join(cells).lower()
                if "ký hiệu" in cells_text and "số hóa đơn" in cells_text:
                    continue

                invoice = self._extract_invoice_from_cells(cells, col_map, row_id)
                if invoice:
                    invoices.append(invoice)

            _logger.info("Parsed %d invoices from HTML table", len(invoices))

        except Exception as e:
            _logger.error("Error parsing invoice HTML: %s", e, exc_info=True)

        has_more = len(invoices) >= page_size
        next_page_pattern = r'page=%d' % (page + 1)
        if next_page_pattern in html or '>>' in html:
            has_more = True

        return {"invoices": invoices, "total": len(invoices), "has_more": has_more}

    def _detect_column_map(self, headers):
        """Detect column positions from header text."""
        col_map = {}

        for i, h in enumerate(headers):
            h_lower = h.lower().strip()
            if not h_lower:
                continue

            if h_lower in ("stt", "no", "no.", "#"):
                col_map["stt"] = i
            elif "ký hiệu" in h_lower or "symbol" in h_lower or "series" in h_lower:
                col_map["series"] = i
            elif ("số" in h_lower and "hóa đơn" in h_lower) or \
                 ("invoice" in h_lower and "number" in h_lower):
                col_map["invoice_number"] = i
            elif "số" in h_lower and "hóa" not in h_lower and "invoice_number" not in col_map:
                col_map.setdefault("invoice_number", i)
            elif "ngày" in h_lower or "date" in h_lower:
                col_map["date"] = i
            elif "người mua" in h_lower or "buyer" in h_lower or "khách" in h_lower:
                if "mst" in h_lower or "mã số" in h_lower or "tax" in h_lower:
                    col_map["buyer_tax"] = i
                else:
                    col_map["buyer_name"] = i
            elif any(kw in h_lower for kw in ("mst", "mã số thuế", "tax code", "tax_code")):
                col_map["buyer_tax"] = i
            elif any(kw in h_lower for kw in ("tổng", "tiền", "total", "amount", "thành tiền")):
                col_map["total_amount"] = i
            elif "trạng thái" in h_lower or "status" in h_lower:
                col_map["status"] = i
            elif "người bán" in h_lower or "seller" in h_lower:
                col_map["seller_name"] = i

        # Fallback default positions
        if not col_map:
            _logger.info("Using default column positions (no headers matched)")
            col_map = {
                "stt": 0, "series": 1, "invoice_number": 2,
                "date": 3, "buyer_name": 4, "buyer_tax": 5,
                "total_amount": 6, "status": 7,
            }

        return col_map

    def _extract_invoice_from_cells(self, cells, col_map, row_id=""):
        """Extract invoice data from table cells using column mapping."""
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

        if not invoice_number and not row_id:
            return None

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
                data.get("data", []) or data.get("items", [])
                or data.get("invoices", []) or data.get("Data", []) or []
            )
        else:
            raw_list = []

        for item in raw_list:
            invoice = self._normalize_invoice_json(item)
            if invoice:
                invoices.append(invoice)

        total = data.get("total", len(invoices)) if isinstance(data, dict) else len(invoices)
        return {"invoices": invoices, "total": total, "has_more": len(invoices) >= 50}

    def _normalize_invoice_json(self, raw):
        """Normalize a raw invoice dict from JSON API response."""
        if not raw:
            return None

        invoice_id = raw.get("id") or raw.get("Id") or raw.get("invoiceId") or raw.get("InvoiceId") or ""
        invoice_number = (
            raw.get("invoiceNumber") or raw.get("InvoiceNumber")
            or raw.get("invoice_number") or raw.get("SoHoaDon")
            or str(invoice_id)
        )
        invoice_date = (
            raw.get("invoiceDate") or raw.get("InvoiceDate")
            or raw.get("invoice_date") or raw.get("NgayHoaDon") or ""
        )
        total_amount = float(
            raw.get("totalAmount") or raw.get("TotalAmount")
            or raw.get("total_amount") or raw.get("TongTien") or 0
        )
        buyer_name = raw.get("buyerName") or raw.get("BuyerName") or raw.get("buyer_name") or ""
        buyer_tax = raw.get("buyerTaxCode") or raw.get("BuyerTaxCode") or raw.get("buyer_tax_code") or ""
        seller_name = raw.get("sellerName") or raw.get("SellerName") or raw.get("seller_name") or ""
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
            cleaned = str(amount_str).strip()
            cleaned = cleaned.replace(".", "").replace(",", ".")
            cleaned = re.sub(r"[^\d.\-]", "", cleaned)
            return float(cleaned) if cleaned else 0.0
        except (ValueError, AttributeError):
            return 0.0

    # ------------------------------------------------------------------
    # File Download
    # ------------------------------------------------------------------

    def download_invoice_files(self, invoice_ids, allow_pdf=True, allow_xml=True):
        """Download invoice files (PDF/XML) as a ZIP archive."""
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
                timeout=DOWNLOAD_TIMEOUT,
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

            _logger.warning(
                "Download response: HTTP %d, size: %d bytes",
                response.status_code, len(response.content),
            )
            return None

        except requests.RequestException as e:
            _logger.error("Download request failed: %s", e)
            raise

    def download_report_data(self, date_from, date_to):
        """Download invoice report data (Excel/CSV) for a date range."""
        if not self._authenticated:
            raise ValueError("Not authenticated.")

        _logger.info("Downloading report data: %s to %s", date_from, date_to)

        payload = {"dateFrom": date_from, "dateTo": date_to}

        try:
            response = self._session.post(
                self._url(INVOICE_REPORT_PATH),
                data=payload,
                timeout=DOWNLOAD_TIMEOUT,
                headers={
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self._url(INVOICE_LIST_PATH),
                },
            )

            if response.status_code == 200 and len(response.content) > 100:
                _logger.info("Downloaded report: %d bytes", len(response.content))
                return response.content

            _logger.warning(
                "Report download: HTTP %d, size: %d",
                response.status_code, len(response.content),
            )
            return None

        except requests.RequestException as e:
            _logger.error("Report download failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def logout(self):
        """Log out from the portal and clear session."""
        try:
            self._session.get(self._url(LOGOUT_PATH), timeout=REQUEST_TIMEOUT)
        except Exception:
            pass
        finally:
            self._authenticated = False
            self._auth_time = None
            self._csrf_token = None
            self._session.cookies.clear()
            _logger.info("Logged out from Grab e-invoice portal")
