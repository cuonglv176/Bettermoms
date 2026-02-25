/**
 * tracuu-scraper.js
 * Trích xuất dữ liệu hóa đơn từ spv.tracuuhoadon.online
 *
 * Credentials: ID: 0108951191 / Pass: Ntptech*1019
 */

import { parseAmount, normalizeDate } from '../utils/validators.js';
import { downloadPdfAsBase64, generatePdfFilename } from '../utils/pdf-handler.js';

const SPV_BASE_URL = 'https://spv.tracuuhoadon.online';
const SPV_API_BASE = `${SPV_BASE_URL}/api`;

const ENDPOINTS = {
  LOGIN: '/auth/login',
  INVOICE_LIST: '/hoa-don/danh-sach',
  INVOICE_DETAIL: '/hoa-don/{id}',
  INVOICE_DOWNLOAD_PDF: '/hoa-don/{id}/pdf',
  INVOICE_DOWNLOAD_XML: '/hoa-don/{id}/xml',
};

/**
 * TracuuScraper - Lấy hóa đơn từ SPV Tracuuhoadon portal.
 */
export class TracuuScraper {
  constructor() {
    this.authToken = null;
    this.isAuthenticated = false;
    this.csrfToken = null;
  }

  /**
   * Đăng nhập vào SPV Tracuuhoadon.
   * @param {string} username - MST: 0108951191
   * @param {string} password
   * @returns {boolean}
   */
  async login(username, password) {
    try {
      // Lấy trang đăng nhập để lấy CSRF token
      const loginPageResp = await fetch(`${SPV_BASE_URL}/dang-nhap`, {
        credentials: 'include',
      });
      const html = await loginPageResp.text();
      this.csrfToken = this._extractCsrfToken(html);

      // Thử API login trước
      const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      };
      if (this.csrfToken) {
        headers['X-CSRF-Token'] = this.csrfToken;
      }

      const apiResp = await fetch(`${SPV_API_BASE}${ENDPOINTS.LOGIN}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      });

      if (apiResp.ok) {
        const data = await apiResp.json();
        this.authToken = data.token || data.access_token || data.jwt || null;
        this.isAuthenticated = true;
        console.log('[TracuuScraper] Đăng nhập API thành công');
        return true;
      }

      // Fallback: form-based login
      const formHeaders = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': `${SPV_BASE_URL}/dang-nhap`,
      };
      if (this.csrfToken) {
        formHeaders['X-CSRF-Token'] = this.csrfToken;
      }

      const formData = new URLSearchParams({ username, password });
      if (this.csrfToken) formData.append('_token', this.csrfToken);

      const formResp = await fetch(`${SPV_BASE_URL}/dang-nhap`, {
        method: 'POST',
        headers: formHeaders,
        body: formData.toString(),
        credentials: 'include',
        redirect: 'follow',
      });

      this.isAuthenticated = formResp.ok || formResp.redirected;
      console.log('[TracuuScraper] Đăng nhập form:', this.isAuthenticated ? 'thành công' : 'thất bại');
      return this.isAuthenticated;
    } catch (error) {
      console.error('[TracuuScraper] Lỗi đăng nhập:', error);
      return false;
    }
  }

  /**
   * Lấy danh sách hóa đơn.
   * @param {number} days - Số ngày cần lấy
   * @returns {Array}
   */
  async fetchInvoices(days = 30) {
    if (!this.isAuthenticated) {
      throw new Error('Chưa đăng nhập vào SPV Tracuuhoadon');
    }

    const dateTo = new Date();
    const dateFrom = new Date();
    dateFrom.setDate(dateFrom.getDate() - days);

    const formatDate = (d) => {
      const dd = String(d.getDate()).padStart(2, '0');
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const yyyy = d.getFullYear();
      return `${dd}/${mm}/${yyyy}`;
    };

    const invoices = [];
    let page = 1;
    let hasMore = true;

    while (hasMore) {
      try {
        const params = new URLSearchParams({
          tu_ngay: formatDate(dateFrom),
          den_ngay: formatDate(dateTo),
          trang: page,
          so_luong: 50,
        });

        const headers = {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        };
        if (this.authToken) {
          headers['Authorization'] = `Bearer ${this.authToken}`;
        }
        if (this.csrfToken) {
          headers['X-CSRF-Token'] = this.csrfToken;
        }

        const response = await fetch(
          `${SPV_API_BASE}${ENDPOINTS.INVOICE_LIST}?${params}`,
          { headers, credentials: 'include' }
        );

        if (!response.ok) {
          // Thử scrape HTML nếu API không hoạt động
          const htmlInvoices = await this._scrapeHtmlList(dateFrom, dateTo, page);
          if (htmlInvoices.length > 0) {
            invoices.push(...htmlInvoices);
          }
          hasMore = false;
          break;
        }

        const data = await response.json();
        const pageInvoices = this._parseInvoiceList(data);

        if (pageInvoices.length === 0) {
          hasMore = false;
        } else {
          invoices.push(...pageInvoices);
          page++;
          const total = data.total || data.tong_so || 0;
          hasMore = invoices.length < total && pageInvoices.length === 50;
        }
      } catch (error) {
        console.error('[TracuuScraper] Lỗi lấy trang', page, ':', error);
        break;
      }
    }

    console.log(`[TracuuScraper] Lấy được ${invoices.length} hóa đơn từ SPV`);
    return invoices;
  }

  /**
   * Scrape danh sách hóa đơn từ HTML (fallback).
   */
  async _scrapeHtmlList(dateFrom, dateTo, page) {
    try {
      const formatDate = (d) => {
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        return `${dd}/${mm}/${d.getFullYear()}`;
      };

      const params = new URLSearchParams({
        tu_ngay: formatDate(dateFrom),
        den_ngay: formatDate(dateTo),
        trang: page,
      });

      const response = await fetch(
        `${SPV_BASE_URL}/hoa-don?${params}`,
        { credentials: 'include' }
      );

      if (!response.ok) return [];

      const html = await response.text();
      return this._parseHtmlTable(html);
    } catch (error) {
      console.error('[TracuuScraper] Lỗi scrape HTML:', error);
      return [];
    }
  }

  /**
   * Parse bảng HTML để lấy dữ liệu hóa đơn.
   */
  _parseHtmlTable(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const rows = doc.querySelectorAll('table tbody tr, .invoice-list .invoice-item');
    const invoices = [];

    rows.forEach(row => {
      const cells = row.querySelectorAll('td');
      if (cells.length < 5) return;

      const invoice = {
        source: 'tracuu',
        external_id: row.dataset.id || row.getAttribute('data-id') || '',
        invoice_number: cells[0]?.textContent?.trim() || '',
        invoice_code: cells[1]?.textContent?.trim() || '',
        invoice_symbol: cells[2]?.textContent?.trim() || '',
        invoice_date: normalizeDate(cells[3]?.textContent?.trim() || ''),
        seller_tax_code: cells[4]?.textContent?.trim() || '',
        seller_name: cells[5]?.textContent?.trim() || '',
        amount_total: parseAmount(cells[6]?.textContent?.trim() || '0'),
        amount_untaxed: 0,
        amount_tax: 0,
        pdf_url: null,
        pdf_base64: null,
        pdf_filename: null,
        pdf_status: 'pending',
      };

      // Lấy link PDF nếu có
      const pdfLink = row.querySelector('a[href*="pdf"], a[href*="download"]');
      if (pdfLink) {
        invoice.pdf_url = pdfLink.href;
      }

      if (invoice.invoice_number) {
        invoices.push(invoice);
      }
    });

    return invoices;
  }

  /**
   * Tải file PDF cho một hóa đơn.
   */
  async downloadInvoicePdf(invoice) {
    try {
      const pdfUrl = invoice.pdf_url ||
        `${SPV_API_BASE}${ENDPOINTS.INVOICE_DOWNLOAD_PDF.replace('{id}', invoice.external_id)}`;

      const headers = {};
      if (this.authToken) {
        headers['Authorization'] = `Bearer ${this.authToken}`;
      }

      const result = await downloadPdfAsBase64(pdfUrl, headers);

      if (result.success) {
        return {
          pdf_base64: result.base64,
          pdf_filename: result.filename || generatePdfFilename(invoice.invoice_number, 'tracuu'),
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
      const xmlUrl = `${SPV_API_BASE}${ENDPOINTS.INVOICE_DOWNLOAD_XML.replace('{id}', invoice.external_id)}`;

      const headers = {};
      if (this.authToken) {
        headers['Authorization'] = `Bearer ${this.authToken}`;
      }

      const response = await fetch(xmlUrl, { headers, credentials: 'include' });
      if (!response.ok) return { xml_base64: null };

      const blob = await response.blob();
      const reader = new FileReader();
      const base64 = await new Promise((resolve) => {
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.readAsDataURL(blob);
      });

      return {
        xml_base64: base64,
        xml_filename: `invoice_${invoice.invoice_number}.xml`,
      };
    } catch (error) {
      return { xml_base64: null };
    }
  }

  _parseInvoiceList(data) {
    const items = data.data || data.items || data.hoa_don || data.result || [];
    if (!Array.isArray(items)) return [];
    return items.map(item => this._parseInvoiceItem(item)).filter(Boolean);
  }

  _parseInvoiceItem(raw) {
    if (!raw) return null;
    const invoiceNumber = raw.so_hoa_don || raw.invoiceNumber || raw.invoice_number || '';
    if (!invoiceNumber) return null;

    return {
      source: 'tracuu',
      external_id: String(raw.id || ''),
      invoice_number: String(invoiceNumber),
      invoice_code: String(raw.ma_tra_cuu || raw.invoiceCode || ''),
      invoice_symbol: String(raw.ky_hieu || raw.invoiceSymbol || ''),
      invoice_date: normalizeDate(raw.ngay_lap || raw.invoiceDate || ''),
      seller_tax_code: String(raw.mst_ncc || raw.sellerTaxCode || ''),
      seller_name: String(raw.ten_ncc || raw.sellerName || ''),
      amount_untaxed: parseAmount(raw.tien_truoc_thue || raw.amountUntaxed || 0),
      amount_tax: parseAmount(raw.tien_thue || raw.amountTax || 0),
      amount_total: parseAmount(raw.tong_tien || raw.amountTotal || 0),
      pdf_url: raw.link_pdf || raw.pdfUrl || null,
      pdf_base64: null,
      pdf_filename: null,
      pdf_status: 'pending',
    };
  }

  _extractCsrfToken(html) {
    const match = html.match(/name="_token"\s+value="([^"]+)"/);
    return match ? match[1] : null;
  }
}
