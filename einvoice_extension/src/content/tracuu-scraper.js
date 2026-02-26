/**
 * tracuu-scraper.js
 * Trích xuất dữ liệu hóa đơn từ spv.tracuuhoadon.online
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập.
 *
 * Cấu trúc bảng thực tế (từ screenshot):
 * STT | Thao tác (Xem | Tải về) | Số hóa đơn | Mẫu số | Ký hiệu | Ngày HĐ | Tổng tiền | Ký
 *  0  |          1              |      2      |    3   |    4    |    5    |     6     |  7
 *
 * Bảng dùng DataTable jQuery plugin.
 * URL: https://spv.tracuuhoadon.online/danh-sach-hoa-don
 */

class TracuuScraper {
  constructor() {
    this.source = 'tracuu';
  }

  /**
   * Kiểm tra trang đã đăng nhập chưa.
   */
  isLoggedIn() {
    // Nếu đang ở trang đăng nhập → chưa đăng nhập
    if (window.location.pathname.includes('dang-nhap') ||
        window.location.pathname === '/' ||
        window.location.pathname === '') {
      return false;
    }
    // Kiểm tra có bảng dữ liệu trên trang không
    const hasTable = document.querySelector('table') !== null;
    // Kiểm tra URL có chứa danh-sach hoặc hoa-don
    const isInvoicePage = window.location.pathname.includes('danh-sach') ||
                          window.location.pathname.includes('hoa-don') ||
                          window.location.pathname.includes('bien-ban');
    // Kiểm tra có menu đăng xuất không
    const bodyText = document.body ? document.body.innerText : '';
    const hasLogout = bodyText.includes('Đăng xuất') || bodyText.includes('đăng xuất');

    console.log('[TracuuScraper] isLoggedIn check:', {
      path: window.location.pathname,
      hasTable,
      isInvoicePage,
      hasLogout,
    });

    return hasTable || isInvoicePage || hasLogout;
  }

  /**
   * Lấy danh sách hóa đơn từ bảng HTML trên trang hiện tại.
   * @returns {Array} Danh sách hóa đơn
   */
  scrapeInvoices() {
    const invoices = [];

    // Debug: log toàn bộ bảng trên trang
    const allTables = document.querySelectorAll('table');
    console.log(`[TracuuScraper] Tổng số bảng: ${allTables.length}`);
    allTables.forEach((t, i) => {
      const ths = Array.from(t.querySelectorAll('th')).map(h => h.textContent.trim());
      const rowCount = t.querySelectorAll('tbody tr').length;
      console.log(`[TracuuScraper] Bảng ${i}: ${rowCount} rows, headers:`, ths);
    });

    if (allTables.length === 0) {
      console.warn('[TracuuScraper] Không tìm thấy bảng nào. Trang có thể chưa load xong.');
      return invoices;
    }

    // Tìm bảng chứa hóa đơn
    let invoiceTable = null;

    // Ưu tiên 1: Tìm bảng có header "Số hóa đơn"
    for (const table of allTables) {
      const headers = Array.from(table.querySelectorAll('th'));
      const headerTexts = headers.map(h => h.textContent.trim().toLowerCase());
      console.log('[TracuuScraper] Kiểm tra headers:', headerTexts);
      if (headerTexts.some(h =>
        h.includes('số hóa đơn') ||
        h.includes('so hoa don') ||
        h.includes('số hđ') ||
        h === 'số hd'
      )) {
        invoiceTable = table;
        console.log('[TracuuScraper] Tìm thấy bảng hóa đơn qua header "Số hóa đơn"');
        break;
      }
    }

    // Ưu tiên 2: Tìm bảng có DataTable ID
    if (!invoiceTable) {
      const dtTable = document.querySelector('#tblHoaDon, #invoiceTable, table.dataTable, table[id*="hoa"], table[id*="invoice"]');
      if (dtTable) {
        invoiceTable = dtTable;
        console.log('[TracuuScraper] Tìm thấy bảng qua DataTable ID');
      }
    }

    // Ưu tiên 3: Lấy bảng có nhiều cột nhất (>= 5 cột)
    if (!invoiceTable) {
      let maxCols = 0;
      for (const table of allTables) {
        const colCount = table.querySelectorAll('th').length ||
                         table.querySelectorAll('tr:first-child td').length;
        if (colCount > maxCols && colCount >= 5) {
          maxCols = colCount;
          invoiceTable = table;
        }
      }
      if (invoiceTable) {
        console.log(`[TracuuScraper] Fallback: dùng bảng có nhiều cột nhất (${maxCols} cột)`);
      }
    }

    if (!invoiceTable) {
      console.warn('[TracuuScraper] Không tìm thấy bảng hóa đơn phù hợp');
      return invoices;
    }

    // Xác định vị trí các cột
    const headers = Array.from(invoiceTable.querySelectorAll('thead th, th'));
    console.log('[TracuuScraper] Headers của bảng đã chọn:', headers.map(h => h.textContent.trim()));
    const colMap = this._mapColumns(headers);
    console.log('[TracuuScraper] Column mapping:', colMap);

    // Lấy dữ liệu từ các hàng tbody
    const rows = invoiceTable.querySelectorAll('tbody tr');
    console.log(`[TracuuScraper] Số hàng tbody: ${rows.length}`);

    // Nếu không có tbody, thử lấy tất cả tr (bỏ qua hàng đầu nếu là header)
    const dataRows = rows.length > 0 ? rows : Array.from(invoiceTable.querySelectorAll('tr')).slice(1);
    console.log(`[TracuuScraper] Số hàng dữ liệu: ${dataRows.length}`);

    dataRows.forEach((row, index) => {
      try {
        const cells = row.querySelectorAll('td');
        if (cells.length < 3) {
          console.log(`[TracuuScraper] Bỏ qua hàng ${index}: chỉ có ${cells.length} cells`);
          return;
        }

        // Debug: log nội dung hàng đầu tiên
        if (index === 0) {
          const cellTexts = Array.from(cells).map(c => c.textContent.trim().substring(0, 30));
          console.log('[TracuuScraper] Hàng đầu tiên:', cellTexts);
        }

        const invoice = this._parseRow(cells, colMap, row);
        if (invoice) {
          if (!invoice.invoice_number) {
            console.warn(`[TracuuScraper] Hàng ${index}: Không lấy được số hóa đơn. colMap.so_hoa_don=${colMap.so_hoa_don}, cell text="${cells[colMap.so_hoa_don] ? cells[colMap.so_hoa_don].textContent.trim() : 'N/A'}"`);
          } else {
            invoice._id = `tracuu_${index}_${Date.now()}`;
            invoices.push(invoice);
          }
        }
      } catch (err) {
        console.warn(`[TracuuScraper] Lỗi parse hàng ${index}:`, err.message);
      }
    });

    console.log(`[TracuuScraper] Kết quả: ${invoices.length} hóa đơn`);
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
      const text = th.textContent.trim().toLowerCase()
        .replace(/\s+/g, ' ')
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '') // bỏ dấu để so sánh
        .replace(/đ/g, 'd');

      const original = th.textContent.trim().toLowerCase();

      if (original === 'stt' || original === '#' || original === 'no.') {
        map.stt = idx;
      } else if (original.includes('thao tác') || original.includes('thao tac') || original.includes('action') || original.includes('tác vụ')) {
        map.thao_tac = idx;
      } else if (original.includes('số hóa đơn') || original.includes('so hoa don') || original.includes('số hđ') || original.includes('số hd') || original.includes('invoice no') || original.includes('invoice number')) {
        map.so_hoa_don = idx;
      } else if (original.includes('mẫu số') || original.includes('mau so') || original.includes('template') || original.includes('form')) {
        map.mau_so = idx;
      } else if (original.includes('ký hiệu') || original.includes('ky hieu') || original.includes('serial') || original.includes('symbol') || original.includes('kí hiệu')) {
        map.ky_hieu = idx;
      } else if (original.includes('ngày') || original.includes('date') || original.includes('ngay')) {
        map.ngay_hd = idx;
      } else if (original.includes('tổng tiền') || original.includes('tong tien') || original.includes('thành tiền') || original.includes('amount') || original.includes('total') || original.includes('tiền')) {
        map.tong_tien = idx;
      } else if (original === 'ký' || original === 'ky' || original === 'sign' || original === 'signed') {
        map.ky = idx;
      } else if (original.includes('mã số thuế') || original.includes('mst') || original.includes('tax code')) {
        map.mst = idx;
      } else if ((original.includes('tên') || original.includes('ten')) && (original.includes('bán') || original.includes('ban') || original.includes('ncc') || original.includes('seller') || original.includes('vendor'))) {
        map.ten_ncc = idx;
      }
    });

    // Fallback cứng cho bảng tracuuhoadon chuẩn:
    // STT(0) | Thao tác(1) | Số hóa đơn(2) | Mẫu số(3) | Ký hiệu(4) | Ngày HĐ(5) | Tổng tiền(6) | Ký(7)
    if (map.so_hoa_don === -1) {
      console.log('[TracuuScraper] Không detect được cột "Số hóa đơn", dùng fallback cứng');
      if (headers.length >= 7) {
        map.stt = 0;
        map.thao_tac = 1;
        map.so_hoa_don = 2;
        map.mau_so = 3;
        map.ky_hieu = 4;
        map.ngay_hd = 5;
        map.tong_tien = 6;
        if (headers.length >= 8) map.ky = 7;
      } else if (headers.length >= 5) {
        // Bảng ít cột hơn, thử tìm cột số
        map.so_hoa_don = 1; // Thường là cột thứ 2 sau STT
        map.ngay_hd = 2;
        map.tong_tien = 3;
      }
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

    // Lấy số hóa đơn
    let invoiceNumber = getText(colMap.so_hoa_don);

    // Nếu vẫn không có, thử tìm trong tất cả cells (tìm cell có dạng số)
    if (!invoiceNumber) {
      for (let i = 0; i < cells.length; i++) {
        const text = cells[i].textContent.trim();
        // Số hóa đơn thường là số nguyên hoặc có dạng như "185517", "100611"
        if (/^\d{4,10}$/.test(text)) {
          invoiceNumber = text;
          console.log(`[TracuuScraper] Tìm thấy số hóa đơn ở cột ${i}: ${text}`);
          break;
        }
      }
    }

    if (!invoiceNumber) return null;

    // Lấy link PDF/download từ cột thao tác
    let pdfUrl = null;
    let viewUrl = null;

    // Tìm trong cột thao tác
    if (colMap.thao_tac >= 0 && colMap.thao_tac < cells.length) {
      const links = cells[colMap.thao_tac].querySelectorAll('a');
      links.forEach(link => {
        const linkText = link.textContent.trim().toLowerCase();
        const href = link.href || link.getAttribute('href') || '';
        if (linkText.includes('tải') || linkText.includes('download') || href.includes('download') || href.includes('pdf') || href.includes('tai-ve')) {
          pdfUrl = href;
        }
        if (linkText.includes('xem') || linkText.includes('view')) {
          viewUrl = href;
        }
      });
    }

    // Tìm trong toàn bộ hàng nếu chưa có
    if (!pdfUrl) {
      const allLinks = row.querySelectorAll('a');
      allLinks.forEach(link => {
        const href = link.href || link.getAttribute('href') || '';
        const text = link.textContent.trim().toLowerCase();
        if (text.includes('tải về') || text.includes('download') || href.includes('pdf') || href.includes('download') || href.includes('tai-ve')) {
          pdfUrl = href;
        }
        if (!viewUrl && (text.includes('xem') || text.includes('view'))) {
          viewUrl = href;
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
      invoice_code: '',
      invoice_symbol: getText(colMap.ky_hieu),
      invoice_date: normalizedDate,
      seller_tax_code: getText(colMap.mst) || '',
      seller_name: getText(colMap.ten_ncc) || '',
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
   */
  async downloadPdf(invoice) {
    if (!invoice.pdf_url && !invoice.view_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }

    const url = invoice.pdf_url || invoice.view_url;

    try {
      const response = await fetch(url, {
        credentials: 'include',
        headers: { 'Accept': 'application/pdf,application/octet-stream,*/*' },
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

      return { pdf_base64: base64, pdf_filename: filename, pdf_status: 'downloaded' };
    } catch (err) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: err.message };
    }
  }

  _parseAmount(str) {
    if (!str) return 0;
    // Xử lý format VN: 176.843 → 176843
    const cleaned = str.replace(/\./g, '').replace(/,/g, '.').replace(/[^\d.-]/g, '');
    return parseFloat(cleaned) || 0;
  }

  _normalizeDate(str) {
    if (!str) return null;
    const trimmed = str.trim();
    const m1 = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (m1) return `${m1[3]}-${m1[2].padStart(2,'0')}-${m1[1].padStart(2,'0')}`;
    const m2 = trimmed.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
    if (m2) return `${m2[3]}-${m2[2].padStart(2,'0')}-${m2[1].padStart(2,'0')}`;
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
    return null;
  }

  _blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = () => reject(new Error('Lỗi đọc file'));
      reader.readAsDataURL(blob);
    });
  }
}

if (typeof window !== 'undefined') {
  window.TracuuScraper = TracuuScraper;
}
