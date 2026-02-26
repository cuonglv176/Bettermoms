/**
 * tracuu-scraper.js
 * Trích xuất dữ liệu hóa đơn từ spv.tracuuhoadon.online
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập.
 *
 * Cấu trúc bảng (từ phân tích thực tế):
 * Cột: STT | Thao tác (Xem | Tải về) | Số hóa đơn | Mẫu số | Ký hiệu | Ngày HĐ | Tổng tiền | Ký
 * Bảng dùng DataTable plugin (jQuery)
 */

/**
 * TracuuScraper - Scrape hóa đơn trực tiếp từ DOM trang tracuuhoadon.
 * Chạy trong context của content script (có quyền truy cập DOM).
 */
class TracuuScraper {
  constructor() {
    this.source = 'tracuu';
  }

  /**
   * Kiểm tra trang đã đăng nhập chưa.
   */
  isLoggedIn() {
    // Nếu đang ở trang đăng nhập thì chưa đăng nhập
    if (window.location.pathname.includes('dang-nhap')) {
      return false;
    }
    // Kiểm tra có bảng dữ liệu hoặc menu user không
    const hasTable = document.querySelector('table') !== null;
    const hasUserMenu = document.querySelector('.dropdown-toggle, .user-info, [class*="user"], [class*="account"]') !== null;
    const hasInvoiceList = window.location.pathname.includes('danh-sach') || window.location.pathname.includes('hoa-don');
    return hasTable || hasUserMenu || hasInvoiceList;
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
      console.warn('[TracuuScraper] Không tìm thấy bảng nào trên trang');
      return invoices;
    }

    // Tìm bảng chứa hóa đơn (bảng có cột "Số hóa đơn")
    let invoiceTable = null;
    for (const table of tables) {
      const headers = table.querySelectorAll('th');
      const headerTexts = Array.from(headers).map(h => h.textContent.trim().toLowerCase());
      if (headerTexts.some(h => h.includes('số hóa đơn') || h.includes('so hoa don') || h.includes('số hđ'))) {
        invoiceTable = table;
        break;
      }
    }

    if (!invoiceTable) {
      // Fallback: lấy bảng đầu tiên có nhiều hơn 3 cột
      for (const table of tables) {
        const headers = table.querySelectorAll('th');
        if (headers.length >= 5) {
          invoiceTable = table;
          break;
        }
      }
    }

    if (!invoiceTable) {
      console.warn('[TracuuScraper] Không tìm thấy bảng hóa đơn');
      return invoices;
    }

    // Xác định vị trí các cột dựa trên header
    const headers = Array.from(invoiceTable.querySelectorAll('thead th, th'));
    const colMap = this._mapColumns(headers);

    console.log('[TracuuScraper] Column mapping:', colMap);

    // Lấy dữ liệu từ các hàng
    const rows = invoiceTable.querySelectorAll('tbody tr');
    console.log(`[TracuuScraper] Tìm thấy ${rows.length} hàng trong bảng`);

    rows.forEach((row, index) => {
      try {
        const cells = row.querySelectorAll('td');
        if (cells.length < 4) return; // Bỏ qua hàng quá ngắn

        const invoice = this._parseRow(cells, colMap, row);
        if (invoice && invoice.invoice_number) {
          invoice._id = `tracuu_${index}_${Date.now()}`;
          invoices.push(invoice);
        }
      } catch (err) {
        console.warn(`[TracuuScraper] Lỗi parse hàng ${index}:`, err);
      }
    });

    console.log(`[TracuuScraper] Scrape được ${invoices.length} hóa đơn`);
    return invoices;
  }

  /**
   * Map tên cột sang vị trí index.
   */
  _mapColumns(headers) {
    const map = {
      stt: -1,
      thao_tac: -1,
      so_hoa_don: -1,
      mau_so: -1,
      ky_hieu: -1,
      ngay_hd: -1,
      tong_tien: -1,
      ky: -1,
      mst: -1,
      ten_ncc: -1,
    };

    headers.forEach((th, idx) => {
      const text = th.textContent.trim().toLowerCase();
      if (text.includes('stt') || text === '#') {
        map.stt = idx;
      } else if (text.includes('thao tác') || text.includes('thao_tac') || text.includes('action')) {
        map.thao_tac = idx;
      } else if (text.includes('số hóa đơn') || text.includes('số hđ') || text.includes('so hoa don') || text.includes('invoice no')) {
        map.so_hoa_don = idx;
      } else if (text.includes('mẫu số') || text.includes('mau so') || text.includes('template')) {
        map.mau_so = idx;
      } else if (text.includes('ký hiệu') || text.includes('ky hieu') || text.includes('serial') || text.includes('symbol')) {
        map.ky_hieu = idx;
      } else if (text.includes('ngày') || text.includes('date') || text.includes('ngay')) {
        map.ngay_hd = idx;
      } else if (text.includes('tổng tiền') || text.includes('tong tien') || text.includes('thành tiền') || text.includes('amount') || text.includes('total')) {
        map.tong_tien = idx;
      } else if (text === 'ký' || text === 'sign') {
        map.ky = idx;
      } else if (text.includes('mã số thuế') || text.includes('mst') || text.includes('tax')) {
        map.mst = idx;
      } else if (text.includes('tên') && (text.includes('bán') || text.includes('ncc') || text.includes('seller'))) {
        map.ten_ncc = idx;
      }
    });

    // Fallback cho bảng tracuuhoadon chuẩn:
    // STT(0) | Thao tác(1) | Số hóa đơn(2) | Mẫu số(3) | Ký hiệu(4) | Ngày HĐ(5) | Tổng tiền(6) | Ký(7)
    if (map.so_hoa_don === -1 && headers.length >= 7) {
      map.stt = 0;
      map.thao_tac = 1;
      map.so_hoa_don = 2;
      map.mau_so = 3;
      map.ky_hieu = 4;
      map.ngay_hd = 5;
      map.tong_tien = 6;
      map.ky = 7;
    }

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

    const invoiceNumber = getText(colMap.so_hoa_don);
    if (!invoiceNumber) return null;

    // Lấy link PDF/download từ cột thao tác
    let pdfUrl = null;
    let viewUrl = null;
    if (colMap.thao_tac >= 0 && colMap.thao_tac < cells.length) {
      const links = cells[colMap.thao_tac].querySelectorAll('a');
      links.forEach(link => {
        const linkText = link.textContent.trim().toLowerCase();
        const href = link.href || link.getAttribute('href') || '';
        if (linkText.includes('tải') || linkText.includes('download') || href.includes('download') || href.includes('pdf')) {
          pdfUrl = href;
        }
        if (linkText.includes('xem') || linkText.includes('view')) {
          viewUrl = href;
        }
      });
    }

    // Cũng tìm link PDF/download trong toàn bộ hàng
    if (!pdfUrl) {
      const allLinks = row.querySelectorAll('a');
      allLinks.forEach(link => {
        const href = link.href || link.getAttribute('href') || '';
        const text = link.textContent.trim().toLowerCase();
        if (text.includes('tải về') || text.includes('download') || href.includes('pdf') || href.includes('download')) {
          pdfUrl = href;
        }
      });
    }

    // Parse số tiền
    const amountStr = getText(colMap.tong_tien);
    const amount = this._parseAmount(amountStr);

    // Parse ngày
    const dateStr = getText(colMap.ngay_hd);
    const normalizedDate = this._normalizeDate(dateStr);

    return {
      source: 'tracuu',
      invoice_number: invoiceNumber,
      invoice_code: '', // Tracuuhoadon không hiển thị mã tra cứu trong bảng
      invoice_symbol: getText(colMap.ky_hieu),
      invoice_date: normalizedDate,
      seller_tax_code: getText(colMap.mst),
      seller_name: getText(colMap.ten_ncc),
      amount_untaxed: 0,
      amount_tax: 0,
      amount_total: amount,
      pdf_url: pdfUrl,
      view_url: viewUrl,
      pdf_base64: null,
      pdf_filename: null,
      pdf_status: pdfUrl ? 'pending' : 'no_link',
    };
  }

  /**
   * Tải PDF cho một hóa đơn.
   * @param {Object} invoice
   * @returns {Promise<Object>}
   */
  async downloadPdf(invoice) {
    if (!invoice.pdf_url && !invoice.view_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }

    const url = invoice.pdf_url || invoice.view_url;

    try {
      const response = await fetch(url, {
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
      const filename = `tracuu_${invoice.invoice_number}_${new Date().toISOString().split('T')[0]}.pdf`;

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
   * Parse số tiền từ chuỗi hiển thị.
   */
  _parseAmount(str) {
    if (!str) return 0;
    const cleaned = str.replace(/\./g, '').replace(/,/g, '.').replace(/[^\d.-]/g, '');
    return parseFloat(cleaned) || 0;
  }

  /**
   * Chuẩn hóa ngày sang YYYY-MM-DD.
   */
  _normalizeDate(str) {
    if (!str) return null;
    const trimmed = str.trim();

    // DD/MM/YYYY
    const m1 = trimmed.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m1) return `${m1[3]}-${m1[2]}-${m1[1]}`;

    // DD-MM-YYYY
    const m2 = trimmed.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (m2) return `${m2[3]}-${m2[2]}-${m2[1]}`;

    // YYYY-MM-DD
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
  window.TracuuScraper = TracuuScraper;
}
