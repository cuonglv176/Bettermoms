/**
 * shinhan-scraper.js
 * Trích xuất dữ liệu hóa đơn từ einvoice.shinhan.com.vn
 *
 * Credentials: ID: 0108951191 / Pass: 625843b5
 */

import { parseAmount, normalizeDate } from '../utils/validators.js';
import { downloadPdfAsBase64, generatePdfFilename } from '../utils/pdf-handler.js';

const SHINHAN_BASE_URL = 'https://einvoice.shinhan.com.vn';
const SHINHAN_API_BASE = `${SHINHAN_BASE_URL}/api`;

const ENDPOINTS = {
  LOGIN: '/auth/login',
  INVOICE_LIST: '/invoice/list',
  INVOICE_DETAIL: '/invoice/{id}',
  INVOICE_PDF: '/invoice/{id}/download/pdf',
  INVOICE_XML: '/invoice/{id}/download/xml',
};

/**
 * ShinhanScraper - Lấy hóa đơn từ Shinhan Bank e-invoice portal.
 */
export class ShinhanScraper {
  constructor() {
    this.authToken = null;
    this.refreshToken = null;
    this.isAuthenticated = false;
    this.tokenExpiry = null;
  }

  /**
   * Đăng nhập vào Shinhan e-invoice.
   * @param {string} username - 0108951191
   * @param {string} password - 625843b5
   * @returns {boolean}
   */
  async login(username, password) {
    try {
      // Shinhan thường dùng JWT-based API authentication
      const response = await fetch(`${SHINHAN_API_BASE}${ENDPOINTS.LOGIN}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'Origin': SHINHAN_BASE_URL,
          'Referer': `${SHINHAN_BASE_URL}/#/login`,
        },
        body: JSON.stringify({
          username,
          password,
          remember: false,
        }),
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        this.authToken = data.token || data.access_token || data.accessToken || null;
        this.refreshToken = data.refresh_token || data.refreshToken || null;
        this.isAuthenticated = !!this.authToken;

        if (this.authToken && data.expires_in) {
          this.tokenExpiry = Date.now() + (data.expires_in * 1000);
        }

        console.log('[ShinhanScraper] Đăng nhập thành công');
        return this.isAuthenticated;
      }

      // Thử với payload khác nhau
      const altResponse = await fetch(`${SHINHAN_API_BASE}${ENDPOINTS.LOGIN}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ id: username, pw: password }),
        credentials: 'include',
      });

      if (altResponse.ok) {
        const data = await altResponse.json();
        this.authToken = data.token || data.access_token || data.jwt || null;
        this.isAuthenticated = !!this.authToken;
        return this.isAuthenticated;
      }

      console.warn('[ShinhanScraper] Đăng nhập thất bại, HTTP:', response.status);
      return false;
    } catch (error) {
      console.error('[ShinhanScraper] Lỗi đăng nhập:', error);
      return false;
    }
  }

  /**
   * Kiểm tra và refresh token nếu cần.
   */
  async _ensureValidToken() {
    if (!this.authToken) return false;
    if (this.tokenExpiry && Date.now() > this.tokenExpiry - 60000) {
      // Token sắp hết hạn, refresh
      if (this.refreshToken) {
        try {
          const response = await fetch(`${SHINHAN_API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: this.refreshToken }),
            credentials: 'include',
          });
          if (response.ok) {
            const data = await response.json();
            this.authToken = data.token || data.access_token || this.authToken;
          }
        } catch (e) {
          console.warn('[ShinhanScraper] Lỗi refresh token:', e);
        }
      }
    }
    return true;
  }

  /**
   * Lấy danh sách hóa đơn.
   * @param {number} days - Số ngày cần lấy
   * @returns {Array}
   */
  async fetchInvoices(days = 30) {
    if (!this.isAuthenticated) {
      throw new Error('Chưa đăng nhập vào Shinhan e-invoice');
    }

    await this._ensureValidToken();

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
          fromDate: formatDate(dateFrom),
          toDate: formatDate(dateTo),
          page: page,
          size: 50,
          pageSize: 50,
        });

        const response = await fetch(
          `${SHINHAN_API_BASE}${ENDPOINTS.INVOICE_LIST}?${params}`,
          {
            headers: {
              'Authorization': `Bearer ${this.authToken}`,
              'Accept': 'application/json',
              'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'include',
          }
        );

        if (!response.ok) {
          console.warn('[ShinhanScraper] Lỗi lấy danh sách trang', page, ':', response.status);
          break;
        }

        const data = await response.json();
        const pageInvoices = this._parseInvoiceList(data);

        if (pageInvoices.length === 0) {
          hasMore = false;
        } else {
          invoices.push(...pageInvoices);
          page++;
          const total = data.total || data.totalElements || data.totalCount || 0;
          hasMore = invoices.length < total && pageInvoices.length === 50;
        }
      } catch (error) {
        console.error('[ShinhanScraper] Lỗi lấy trang', page, ':', error);
        break;
      }
    }

    console.log(`[ShinhanScraper] Lấy được ${invoices.length} hóa đơn từ Shinhan`);
    return invoices;
  }

  /**
   * Tải file PDF cho một hóa đơn.
   */
  async downloadInvoicePdf(invoice) {
    try {
      await this._ensureValidToken();

      const pdfUrl = invoice.pdf_url ||
        `${SHINHAN_API_BASE}${ENDPOINTS.INVOICE_PDF.replace('{id}', invoice.external_id)}`;

      const result = await downloadPdfAsBase64(pdfUrl, {
        'Authorization': `Bearer ${this.authToken}`,
      });

      if (result.success) {
        return {
          pdf_base64: result.base64,
          pdf_filename: result.filename || generatePdfFilename(invoice.invoice_number, 'shinhan'),
        };
      }

      return { pdf_base64: null, pdf_filename: null, pdf_error: result.error };
    } catch (error) {
      return { pdf_base64: null, pdf_filename: null, pdf_error: error.message };
    }
  }

  /**
   * Tải file XML cho một hóa đơn.
   */
  async downloadInvoiceXml(invoice) {
    try {
      await this._ensureValidToken();

      const xmlUrl = `${SHINHAN_API_BASE}${ENDPOINTS.INVOICE_XML.replace('{id}', invoice.external_id)}`;

      const response = await fetch(xmlUrl, {
        headers: { 'Authorization': `Bearer ${this.authToken}` },
        credentials: 'include',
      });

      if (!response.ok) return { xml_base64: null };

      const blob = await response.blob();
      const base64 = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.readAsDataURL(blob);
      });

      return {
        xml_base64: base64,
        xml_filename: `shinhan_${invoice.invoice_number}.xml`,
      };
    } catch (error) {
      return { xml_base64: null };
    }
  }

  _parseInvoiceList(data) {
    const items = data.content || data.data || data.items || data.invoices || [];
    if (!Array.isArray(items)) return [];
    return items.map(item => this._parseInvoiceItem(item)).filter(Boolean);
  }

  _parseInvoiceItem(raw) {
    if (!raw) return null;
    const invoiceNumber = raw.invoiceNo || raw.invoiceNumber || raw.invoice_number || '';
    if (!invoiceNumber) return null;

    return {
      source: 'shinhan',
      external_id: String(raw.id || raw.invoiceId || ''),
      invoice_number: String(invoiceNumber),
      invoice_code: String(raw.invoiceCode || raw.lookupCode || ''),
      invoice_symbol: String(raw.invoiceSymbol || raw.serial || ''),
      invoice_date: normalizeDate(raw.invoiceDate || raw.issuedDate || ''),
      seller_tax_code: String(raw.sellerTaxCode || raw.supplierTaxCode || ''),
      seller_name: String(raw.sellerName || raw.supplierName || ''),
      amount_untaxed: parseAmount(raw.amountBeforeTax || raw.subtotal || 0),
      amount_tax: parseAmount(raw.taxAmount || raw.vatAmount || 0),
      amount_total: parseAmount(raw.totalAmount || raw.amount || 0),
      pdf_url: raw.pdfUrl || raw.downloadUrl || null,
      pdf_base64: null,
      pdf_filename: null,
      pdf_status: 'pending',
    };
  }
}
