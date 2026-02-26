/**
 * grab-scraper.js
 * Trích xuất dữ liệu hóa đơn từ vn.einvoice.grab.com
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập.
 *
 * Grab e-invoice portal hiển thị danh sách hóa đơn dạng bảng HTML.
 * User cần đăng nhập trước, sau đó Extension sẽ scrape bảng.
 */

/**
 * GrabScraper - Scrape hóa đơn trực tiếp từ DOM trang Grab.
 * Chạy trong context của content script.
 */
class GrabScraper {
  constructor() {
    this.source = 'grab';
  }

  /**
   * Kiểm tra trang đã đăng nhập chưa.
   */
  isLoggedIn() {
    // Nếu đang ở trang đăng nhập thì chưa
    if (window.location.pathname.includes('dang-nhap') || window.location.pathname.includes('login')) {
      return false;
    }
    // Kiểm tra có bảng dữ liệu hoặc nội dung hóa đơn
    const hasTable = document.querySelector('table') !== null;
    const hasInvoiceContent = document.querySelector('.invoice, .bill, [class*="invoice"], [class*="bill"]') !== null;
    const bodyText = document.body.innerText || '';
    const hasLogout = bodyText.includes('Đăng xuất') || bodyText.includes('Logout') || bodyText.includes('logout');
    return hasTable || hasInvoiceContent || hasLogout;
  }

  /**
   * Lấy danh sách hóa đơn từ bảng HTML trên trang hiện tại.
   * @returns {Array} Danh sách hóa đơn
   */
  scrapeInvoices() {
    const invoices = [];

    // Tìm tất cả bảng trên trang
    const tables = document.querySelectorAll('table');
    if (tables.length === 0) {
      console.warn('[GrabScraper] Không tìm thấy bảng nào trên trang');
      return invoices;
    }

    // Tìm bảng chứa hóa đơn
    let invoiceTable = null;
    for (const table of tables) {
      const headers = table.querySelectorAll('th');
      const headerTexts = Array.from(headers).map(h => h.textContent.trim().toLowerCase());
      // Tìm bảng có cột liên quan đến hóa đơn
      const hasInvoiceCol = headerTexts.some(h =>
        h.includes('số hóa đơn') || h.includes('invoice') || h.includes('số hđ') ||
        h.includes('mã hóa đơn') || h.includes('ký hiệu') || h.includes('serial')
      );
      if (hasInvoiceCol) {
        invoiceTable = table;
        break;
      }
    }

    if (!invoiceTable) {
      // Fallback: lấy bảng có nhiều cột nhất
      let maxCols = 0;
      for (const table of tables) {
        const headers = table.querySelectorAll('th');
        if (headers.length > maxCols && headers.length >= 4) {
          maxCols = headers.length;
          invoiceTable = table;
        }
      }
    }

    if (!invoiceTable) {
      console.warn('[GrabScraper] Không tìm thấy bảng hóa đơn');
      return invoices;
    }

    // Xác định vị trí các cột dựa trên header
    const headers = Array.from(invoiceTable.querySelectorAll('thead th, th'));
    const colMap = this._mapColumns(headers);

    console.log('[GrabScraper] Column mapping:', colMap);

    // Lấy dữ liệu từ các hàng
    const rows = invoiceTable.querySelectorAll('tbody tr');
    console.log(`[GrabScraper] Tìm thấy ${rows.length} hàng trong bảng`);

    rows.forEach((row, index) => {
      try {
        const cells = row.querySelectorAll('td');
        if (cells.length < 3) return;

        const invoice = this._parseRow(cells, colMap, row);
        if (invoice && invoice.invoice_number) {
          invoice._id = `grab_${index}_${Date.now()}`;
          invoices.push(invoice);
        }
      } catch (err) {
        console.warn(`[GrabScraper] Lỗi parse hàng ${index}:`, err);
      }
    });

    console.log(`[GrabScraper] Scrape được ${invoices.length} hóa đơn`);
    return invoices;
  }

  /**
   * Map tên cột sang vị trí index.
   */
  _mapColumns(headers) {
    const map = {
      stt: -1,
      so_hd: -1,
      ma_hd: -1,
      ky_hieu: -1,
      ngay_hd: -1,
      tong_tien: -1,
      mst: -1,
      ten_ncc: -1,
      trang_thai: -1,
      thao_tac: -1,
    };

    headers.forEach((th, idx) => {
      const text = th.textContent.trim().toLowerCase();
      if (text === 'stt' || text === '#' || text === 'no') {
        map.stt = idx;
      } else if (text.includes('số hóa đơn') || text.includes('số hđ') || text.includes('invoice no') || text.includes('invoice number')) {
        map.so_hd = idx;
      } else if (text.includes('mã') && (text.includes('hóa đơn') || text.includes('tra cứu') || text.includes('code'))) {
        map.ma_hd = idx;
      } else if (text.includes('ký hiệu') || text.includes('serial') || text.includes('symbol')) {
        map.ky_hieu = idx;
      } else if (text.includes('ngày') || text.includes('date')) {
        map.ngay_hd = idx;
      } else if (text.includes('tổng') || text.includes('tiền') || text.includes('amount') || text.includes('total')) {
        map.tong_tien = idx;
      } else if (text.includes('mã số thuế') || text.includes('mst') || text.includes('tax code')) {
        map.mst = idx;
      } else if (text.includes('tên') && (text.includes('bán') || text.includes('ncc') || text.includes('seller') || text.includes('vendor'))) {
        map.ten_ncc = idx;
      } else if (text.includes('trạng thái') || text.includes('status')) {
        map.trang_thai = idx;
      } else if (text.includes('thao tác') || text.includes('action') || text.includes('tải') || text.includes('download')) {
        map.thao_tac = idx;
      }
    });

    return map;
  }

  /**
   * Parse một hàng trong bảng thành object hóa đơn.
   */
  _parseRow(cells, colMap, row) {
    const getText = (idx) => {
      if (idx < 0 || idx >= cells.length) return '';
      return cells[idx].textContent.trim();
    };

    // Tìm số hóa đơn - thử nhiều cột
    let invoiceNumber = getText(colMap.so_hd);
    if (!invoiceNumber && colMap.ma_hd >= 0) {
      invoiceNumber = getText(colMap.ma_hd);
    }

    // Nếu vẫn không tìm thấy, thử tìm trong các cell có link
    if (!invoiceNumber) {
      for (let i = 0; i < cells.length; i++) {
        const link = cells[i].querySelector('a');
        if (link) {
          const text = link.textContent.trim();
          if (/^\d+$/.test(text) || /^[A-Z0-9]+$/i.test(text)) {
            invoiceNumber = text;
            break;
          }
        }
      }
    }

    if (!invoiceNumber) return null;

    // Lấy link PDF/download
    let pdfUrl = null;
    const allLinks = row.querySelectorAll('a');
    allLinks.forEach(link => {
      const href = link.href || link.getAttribute('href') || '';
      const text = link.textContent.trim().toLowerCase();
      const onclick = link.getAttribute('onclick') || '';
      if (text.includes('tải') || text.includes('download') || text.includes('pdf') ||
          href.includes('pdf') || href.includes('download') || onclick.includes('download')) {
        pdfUrl = href || onclick;
      }
    });

    // Parse số tiền
    const amountStr = getText(colMap.tong_tien);
    const amount = this._parseAmount(amountStr);

    // Parse ngày
    const dateStr = getText(colMap.ngay_hd);
    const normalizedDate = this._normalizeDate(dateStr);

    return {
      source: 'grab',
      invoice_number: invoiceNumber,
      invoice_code: getText(colMap.ma_hd),
      invoice_symbol: getText(colMap.ky_hieu),
      invoice_date: normalizedDate,
      seller_tax_code: getText(colMap.mst),
      seller_name: getText(colMap.ten_ncc),
      amount_untaxed: 0,
      amount_tax: 0,
      amount_total: amount,
      pdf_url: pdfUrl,
      pdf_base64: null,
      pdf_filename: null,
      pdf_status: pdfUrl ? 'pending' : 'no_link',
    };
  }

  /**
   * Tải PDF cho một hóa đơn.
   */
  async downloadPdf(invoice) {
    if (!invoice.pdf_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }

    try {
      const response = await fetch(invoice.pdf_url, {
        credentials: 'include',
        headers: {
          'Accept': 'application/pdf,application/octet-stream,*/*',
        },
      });

      if (!response.ok) {
        return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: `HTTP ${response.status}` };
      }

      const blob = await response.blob();
      if (blob.size === 0) {
        return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: 'File trống' };
      }

      const base64 = await this._blobToBase64(blob);
      const filename = `grab_${invoice.invoice_number}_${new Date().toISOString().split('T')[0]}.pdf`;

      return {
        pdf_base64: base64,
        pdf_filename: filename,
        pdf_status: 'downloaded',
      };
    } catch (err) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: err.message };
    }
  }

  /**
   * Parse số tiền.
   */
  _parseAmount(str) {
    if (!str) return 0;
    const cleaned = str.replace(/[^\d.,]/g, '');
    if (!cleaned) return 0;
    const lastComma = cleaned.lastIndexOf(',');
    const lastDot = cleaned.lastIndexOf('.');
    let result;
    if (lastComma > lastDot) {
      result = cleaned.replace(/\./g, '').replace(',', '.');
    } else {
      result = cleaned.replace(/,/g, '');
    }
    return parseFloat(result) || 0;
  }

  /**
   * Chuẩn hóa ngày sang YYYY-MM-DD.
   */
  _normalizeDate(str) {
    if (!str) return null;
    const trimmed = str.trim();
    const m1 = trimmed.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m1) return `${m1[3]}-${m1[2]}-${m1[1]}`;
    const m2 = trimmed.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (m2) return `${m2[3]}-${m2[2]}-${m2[1]}`;
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
    return null;
  }

  /**
   * Chuyển Blob sang Base64.
   */
  _blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = () => reject(new Error('Lỗi đọc file'));
      reader.readAsDataURL(blob);
    });
  }
}

// Export cho content script sử dụng
if (typeof window !== 'undefined') {
  window.GrabScraper = GrabScraper;
}
