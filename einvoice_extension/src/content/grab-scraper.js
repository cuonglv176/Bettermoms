/**
 * grab-scraper.js
 * Trích xuất dữ liệu hóa đơn từ vn.einvoice.grab.com
 * Sử dụng Grab API với session authentication.
 *
 * Credentials: ID: hoadon_gfb_1000060199 / Pass: Ntptech*@1019
 */

import { parseAmount, normalizeDate } from '../utils/validators.js';
import { downloadPdfAsBase64, generatePdfFilename } from '../utils/pdf-handler.js';

const GRAB_BASE_URL = 'https://vn.einvoice.grab.com';
const GRAB_API_BASE = `${GRAB_BASE_URL}/api`;

// API Endpoints
const ENDPOINTS = {
  LOGIN: '/auth/login',
  INVOICE_LIST: '/invoices',
  INVOICE_DETAIL: '/invoices/{id}',
  INVOICE_DOWNLOAD: '/invoices/download',
  INVOICE_PDF: '/invoices/{id}/pdf',
};

/**
 * GrabScraper - Lấy hóa đơn từ Grab e-invoice portal.
 */
export class GrabScraper {
  constructor() {
    this.sessionCookies = null;
    this.authToken = null;
    this.isAuthenticated = false;
  }

  /**
   * Đăng nhập vào Grab e-invoice portal.
   * @param {string} username
   * @param {string} password
   * @returns {boolean}
   */
  async login(username, password) {
    try {
      // Lấy CSRF token trước
      const loginPageResponse = await fetch(`${GRAB_BASE_URL}/tai-khoan/dang-nhap`, {
        credentials: 'include',
      });

      // Thực hiện đăng nhập
      const loginResponse = await fetch(`${GRAB_API_BASE}${ENDPOINTS.LOGIN}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'Referer': `${GRAB_BASE_URL}/tai-khoan/dang-nhap`,
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      });

      if (loginResponse.ok) {
        const data = await loginResponse.json();
        this.authToken = data.token || data.access_token || null;
        this.isAuthenticated = true;
        console.log('[GrabScraper] Đăng nhập thành công');
        return true;
      }

      // Fallback: thử form-based login
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const formResponse = await fetch(`${GRAB_BASE_URL}/tai-khoan/dang-nhap`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Referer': `${GRAB_BASE_URL}/tai-khoan/dang-nhap`,
        },
        body: formData.toString(),
        credentials: 'include',
        redirect: 'follow',
      });

      this.isAuthenticated = formResponse.ok || formResponse.redirected;
      return this.isAuthenticated;
    } catch (error) {
      console.error('[GrabScraper] Lỗi đăng nhập:', error);
      return false;
    }
  }

  /**
   * Lấy danh sách hóa đơn trong khoảng thời gian.
   * @param {number} days - Số ngày cần lấy
   * @returns {Array} Danh sách hóa đơn
   */
  async fetchInvoices(days = 30) {
    if (!this.isAuthenticated) {
      throw new Error('Chưa đăng nhập vào Grab');
    }

    const dateTo = new Date();
    const dateFrom = new Date();
    dateFrom.setDate(dateFrom.getDate() - days);

    const formatDate = (d) => d.toISOString().split('T')[0];

    const invoices = [];
    let page = 1;
    let hasMore = true;

    while (hasMore) {
      try {
        const params = new URLSearchParams({
          dateFrom: formatDate(dateFrom),
          dateTo: formatDate(dateTo),
          page: page,
          limit: 50,
        });

        const headers = {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        };

        if (this.authToken) {
          headers['Authorization'] = `Bearer ${this.authToken}`;
        }

        const response = await fetch(
          `${GRAB_API_BASE}${ENDPOINTS.INVOICE_LIST}?${params}`,
          { headers, credentials: 'include' }
        );

        if (!response.ok) {
          console.warn('[GrabScraper] Lỗi lấy danh sách trang', page, ':', response.status);
          break;
        }

        const data = await response.json();
        const pageInvoices = this._parseInvoiceList(data);

        if (pageInvoices.length === 0) {
          hasMore = false;
        } else {
          invoices.push(...pageInvoices);
          page++;
          // Kiểm tra có trang tiếp theo không
          const total = data.total || data.totalCount || 0;
          hasMore = invoices.length < total && pageInvoices.length === 50;
        }
      } catch (error) {
        console.error('[GrabScraper] Lỗi lấy trang', page, ':', error);
        break;
      }
    }

    console.log(`[GrabScraper] Lấy được ${invoices.length} hóa đơn từ Grab`);
    return invoices;
  }

  /**
   * Tải file PDF cho một hóa đơn.
   * @param {Object} invoice - Dữ liệu hóa đơn
   * @returns {Object} { pdf_base64, pdf_filename }
   */
  async downloadInvoicePdf(invoice) {
    try {
      const pdfUrl = invoice.pdf_url ||
        `${GRAB_API_BASE}${ENDPOINTS.INVOICE_PDF.replace('{id}', invoice.external_id)}`;

      const headers = {};
      if (this.authToken) {
        headers['Authorization'] = `Bearer ${this.authToken}`;
      }

      const result = await downloadPdfAsBase64(pdfUrl, headers);

      if (result.success) {
        return {
          pdf_base64: result.base64,
          pdf_filename: result.filename || generatePdfFilename(invoice.invoice_number, 'grab'),
        };
      }

      console.warn('[GrabScraper] Lỗi tải PDF cho', invoice.invoice_number, ':', result.error);
      return { pdf_base64: null, pdf_filename: null, pdf_error: result.error };
    } catch (error) {
      console.error('[GrabScraper] Lỗi tải PDF:', error);
      return { pdf_base64: null, pdf_filename: null, pdf_error: error.message };
    }
  }

  /**
   * Parse danh sách hóa đơn từ API response.
   * @param {Object} data - API response data
   * @returns {Array}
   */
  _parseInvoiceList(data) {
    const items = data.data || data.items || data.invoices || data.result || [];
    if (!Array.isArray(items)) return [];

    return items.map(item => this._parseInvoiceItem(item)).filter(Boolean);
  }

  /**
   * Parse một hóa đơn từ API response.
   * @param {Object} raw - Raw invoice data
   * @returns {Object}
   */
  _parseInvoiceItem(raw) {
    if (!raw) return null;

    const invoiceNumber = raw.invoiceNumber || raw.invoice_number || raw.so_hoa_don || '';
    if (!invoiceNumber) return null;

    return {
      source: 'grab',
      external_id: String(raw.id || raw.invoiceId || ''),
      invoice_number: String(invoiceNumber),
      invoice_code: String(raw.invoiceCode || raw.invoice_code || raw.ma_tra_cuu || ''),
      invoice_symbol: String(raw.invoiceSymbol || raw.invoice_symbol || raw.ky_hieu || ''),
      invoice_date: normalizeDate(
        raw.invoiceDate || raw.invoice_date || raw.ngay_lap || ''
      ),
      seller_tax_code: String(raw.sellerTaxCode || raw.seller_tax_code || raw.mst_ncc || ''),
      seller_name: String(raw.sellerName || raw.seller_name || raw.ten_ncc || ''),
      amount_untaxed: parseAmount(raw.amountUntaxed || raw.amount_untaxed || raw.tien_truoc_thue || 0),
      amount_tax: parseAmount(raw.amountTax || raw.amount_tax || raw.tien_thue || 0),
      amount_total: parseAmount(raw.amountTotal || raw.amount_total || raw.tong_tien || 0),
      pdf_url: raw.pdfUrl || raw.pdf_url || null,
      pdf_base64: null,
      pdf_filename: null,
      pdf_status: 'pending',
    };
  }
}
