/**
 * shinhan-scraper.js
 * Trích xuất dữ liệu hóa đơn từ einvoice.shinhan.com.vn
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập (Angular app).
 *
 * Cấu trúc bảng thực tế (từ screenshot):
 * Tên hàng hóa, dịch vụ | Loại Tiền | Tỷ giá | Cộng tiền hàng hóa, dịch vụ | Thuế suất thuế GTGT | Tiền thuế GTGT | Tổng cộng thanh toán | Tải về | Thao tác
 *
 * Bảng đầy đủ (16 cột):
 * STT | Loại HĐ | MST người bán | Tên người bán | Ký hiệu | Số HĐ | Ngày HĐ | Tên hàng | Loại tiền | Tỷ giá | Cộng tiền | Thuế suất | Tiền thuế | Tổng cộng | Tải về | Thao tác
 *  0  |    1    |       2       |      3        |    4    |   5   |    6    |    7     |     8     |    9   |    10     |    11     |    12     |    13     |   14   |    15
 *
 * URL: https://einvoice.shinhan.com.vn/#/invoice-list
 */

class ShinhanScraper {
  constructor() {
    this.source = 'shinhan';
  }

  /**
   * Kiểm tra trang đã đăng nhập chưa.
   */
  isLoggedIn() {
    const bodyText = document.body ? document.body.innerText : '';

    // Kiểm tra nút đăng xuất
    const allBtns = document.querySelectorAll('button, a, span');
    for (const el of allBtns) {
      const text = el.textContent.trim().toLowerCase();
      if (text.includes('đăng xuất') || text === 'logout' || text === 'sign out') {
        return true;
      }
    }

    // Kiểm tra text "Chào mừng" hoặc "quý khách"
    if (bodyText.includes('Chào mừng') || bodyText.includes('quý khách') || bodyText.includes('Đăng xuất')) {
      return true;
    }

    // Kiểm tra URL
    if (window.location.hash.includes('invoice-list') || window.location.hash.includes('invoice')) {
      // Nếu có bảng thì đã đăng nhập
      if (document.querySelector('table')) return true;
    }

    console.log('[ShinhanScraper] isLoggedIn check: false. Body snippet:', bodyText.substring(0, 200));
    return false;
  }

  /**
   * Lấy danh sách hóa đơn từ bảng HTML trên trang hiện tại.
   * @returns {Array} Danh sách hóa đơn
   */
  scrapeInvoices() {
    const invoices = [];

    // Debug: log toàn bộ bảng
    const allTables = document.querySelectorAll('table');
    console.log(`[ShinhanScraper] Tổng số bảng: ${allTables.length}`);
    allTables.forEach((t, i) => {
      const ths = Array.from(t.querySelectorAll('th')).map(h => h.textContent.trim());
      const rows = t.querySelectorAll('tbody tr').length;
      console.log(`[ShinhanScraper] Bảng ${i}: ${rows} rows, headers:`, ths);
    });

    if (allTables.length === 0) {
      console.warn('[ShinhanScraper] Không tìm thấy bảng. Angular có thể chưa render xong.');
      return invoices;
    }

    // Tìm bảng chứa hóa đơn
    let invoiceTable = null;

    // Ưu tiên 1: Tìm bảng có header "Số hóa đơn" hoặc "Số HĐ"
    for (const table of allTables) {
      const headers = Array.from(table.querySelectorAll('th'));
      const headerTexts = headers.map(h => h.textContent.trim().toLowerCase());
      if (headerTexts.some(h =>
        h.includes('số hóa đơn') ||
        h.includes('số hđ') ||
        h.includes('so hoa don') ||
        h.includes('invoice no') ||
        h.includes('invoice number')
      )) {
        invoiceTable = table;
        console.log('[ShinhanScraper] Tìm thấy bảng qua header "Số hóa đơn"');
        break;
      }
    }

    // Ưu tiên 2: table.table.table-bordered (class Shinhan)
    if (!invoiceTable) {
      invoiceTable = document.querySelector('table.table.table-bordered') ||
                     document.querySelector('table.table-bordered') ||
                     document.querySelector('table.table');
      if (invoiceTable) console.log('[ShinhanScraper] Tìm thấy bảng qua class Bootstrap');
    }

    // Ưu tiên 3: Bảng có nhiều cột nhất
    if (!invoiceTable) {
      let maxCols = 0;
      for (const table of allTables) {
        const colCount = table.querySelectorAll('th').length;
        if (colCount > maxCols) {
          maxCols = colCount;
          invoiceTable = table;
        }
      }
      if (invoiceTable) console.log(`[ShinhanScraper] Fallback: bảng ${maxCols} cột`);
    }

    if (!invoiceTable) {
      console.warn('[ShinhanScraper] Không tìm thấy bảng hóa đơn');
      return invoices;
    }

    // Xác định vị trí cột
    const headers = Array.from(invoiceTable.querySelectorAll('thead th, th'));
    console.log('[ShinhanScraper] Headers:', headers.map(h => h.textContent.trim()));
    const colMap = this._mapColumns(headers);
    console.log('[ShinhanScraper] Column mapping:', colMap);

    // Lấy dữ liệu
    const rows = invoiceTable.querySelectorAll('tbody tr');
    const dataRows = rows.length > 0 ? rows : Array.from(invoiceTable.querySelectorAll('tr')).slice(1);
    console.log(`[ShinhanScraper] Số hàng dữ liệu: ${dataRows.length}`);

    dataRows.forEach((row, index) => {
      try {
        const cells = row.querySelectorAll('td');
        if (cells.length < 3) return;

        if (index === 0) {
          const cellTexts = Array.from(cells).map(c => c.textContent.trim().substring(0, 30));
          console.log('[ShinhanScraper] Hàng đầu tiên:', cellTexts);
        }

        const invoice = this._parseRow(cells, colMap, row);
        if (invoice) {
          if (!invoice.invoice_number) {
            console.warn(`[ShinhanScraper] Hàng ${index}: Không lấy được số hóa đơn`);
          } else {
            invoice._id = `shinhan_${index}_${Date.now()}`;
            invoices.push(invoice);
          }
        }
      } catch (err) {
        console.warn(`[ShinhanScraper] Lỗi parse hàng ${index}:`, err.message);
      }
    });

    console.log(`[ShinhanScraper] Kết quả: ${invoices.length} hóa đơn`);
    return invoices;
  }

  /**
   * Map tên cột sang vị trí index.
   */
  _mapColumns(headers) {
    const map = {
      stt: -1,
      loai_hd: -1,
      mst_ban: -1,
      ten_ban: -1,
      ky_hieu: -1,
      so_hd: -1,
      ngay_hd: -1,
      ten_hang: -1,
      loai_tien: -1,
      ty_gia: -1,
      cong_tien: -1,
      thue_suat: -1,
      tien_thue: -1,
      tong_cong: -1,
      tai_ve: -1,
      thao_tac: -1,
    };

    headers.forEach((th, idx) => {
      const text = th.textContent.trim().toLowerCase();

      if (text === 'stt' || text === '#') {
        map.stt = idx;
      } else if (text.includes('loại hóa đơn') || text.includes('loại hđ') || text.includes('loai hoa don')) {
        map.loai_hd = idx;
      } else if ((text.includes('mã số thuế') || text.includes('mst')) && text.includes('bán')) {
        map.mst_ban = idx;
      } else if (text.includes('tên người bán') || text.includes('ten nguoi ban') || (text.includes('tên') && text.includes('bán'))) {
        map.ten_ban = idx;
      } else if (text.includes('ký hiệu') || text.includes('ky hieu') || text.includes('kí hiệu')) {
        map.ky_hieu = idx;
      } else if (text.includes('số hóa đơn') || text.includes('số hđ') || text.includes('so hoa don') || text.includes('invoice no')) {
        map.so_hd = idx;
      } else if (text.includes('ngày hóa đơn') || text.includes('ngày hđ') || text.includes('ngay hoa don')) {
        map.ngay_hd = idx;
      } else if (text.includes('tên hàng') || text.includes('dịch vụ') || text.includes('ten hang')) {
        map.ten_hang = idx;
      } else if (text.includes('loại tiền') && !text.includes('cộng')) {
        map.loai_tien = idx;
      } else if (text.includes('tỷ giá') || text.includes('ty gia')) {
        map.ty_gia = idx;
      } else if (text.includes('cộng tiền') || text.includes('tiền hàng') || text.includes('cong tien')) {
        map.cong_tien = idx;
      } else if (text.includes('thuế suất') || text.includes('thue suat')) {
        map.thue_suat = idx;
      } else if (text.includes('tiền thuế') || text.includes('tien thue')) {
        map.tien_thue = idx;
      } else if (text.includes('tổng cộng') || text.includes('thanh toán') || text.includes('tong cong')) {
        map.tong_cong = idx;
      } else if (text.includes('tải về') || text.includes('download') || text.includes('tai ve')) {
        map.tai_ve = idx;
      } else if (text.includes('thao tác') || text.includes('action') || text.includes('thao tac')) {
        map.thao_tac = idx;
      }
    });

    // Fallback cứng cho bảng Shinhan 16 cột chuẩn
    if (map.so_hd === -1) {
      console.log('[ShinhanScraper] Không detect cột, dùng fallback cứng');
      if (headers.length >= 14) {
        map.stt = 0;
        map.loai_hd = 1;
        map.mst_ban = 2;
        map.ten_ban = 3;
        map.ky_hieu = 4;
        map.so_hd = 5;
        map.ngay_hd = 6;
        map.ten_hang = 7;
        map.loai_tien = 8;
        map.ty_gia = 9;
        map.cong_tien = 10;
        map.thue_suat = 11;
        map.tien_thue = 12;
        map.tong_cong = 13;
        if (headers.length >= 15) map.tai_ve = 14;
        if (headers.length >= 16) map.thao_tac = 15;
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

    let invoiceNumber = getText(colMap.so_hd);

    // Fallback: tìm cell có dạng số hóa đơn
    if (!invoiceNumber) {
      for (let i = 0; i < cells.length; i++) {
        const text = cells[i].textContent.trim();
        if (/^\d{4,12}$/.test(text)) {
          invoiceNumber = text;
          console.log(`[ShinhanScraper] Tìm thấy số HĐ ở cột ${i}: ${text}`);
          break;
        }
      }
    }

    if (!invoiceNumber) return null;

    // Lấy link PDF và XML
    let pdfUrl = null;
    let xmlUrl = null;

    // Tìm trong cột "Tải về"
    if (colMap.tai_ve >= 0 && colMap.tai_ve < cells.length) {
      const links = cells[colMap.tai_ve].querySelectorAll('a');
      links.forEach(link => {
        const linkText = link.textContent.trim().toUpperCase();
        const href = link.href || link.getAttribute('href') || '';
        const onclick = link.getAttribute('onclick') || '';
        if (linkText === 'PDF' || href.toLowerCase().includes('pdf')) {
          pdfUrl = href || onclick;
        }
        if (linkText === 'XML' || href.toLowerCase().includes('xml')) {
          xmlUrl = href || onclick;
        }
      });
    }

    // Tìm trong toàn bộ hàng
    if (!pdfUrl || !xmlUrl) {
      const allLinks = row.querySelectorAll('a');
      allLinks.forEach(link => {
        const text = link.textContent.trim().toUpperCase();
        const href = link.href || link.getAttribute('href') || '';
        if (!pdfUrl && (text === 'PDF' || href.toLowerCase().includes('pdf'))) {
          pdfUrl = href;
        }
        if (!xmlUrl && (text === 'XML' || href.toLowerCase().includes('xml'))) {
          xmlUrl = href;
        }
      });
    }

    const amountUntaxed = this._parseAmount(getText(colMap.cong_tien));
    const amountTax = this._parseAmount(getText(colMap.tien_thue));
    const amountTotal = this._parseAmount(getText(colMap.tong_cong));

    return {
      source: 'shinhan',
      invoice_number: invoiceNumber,
      invoice_code: '',
      invoice_symbol: getText(colMap.ky_hieu),
      invoice_date: this._normalizeDate(getText(colMap.ngay_hd)),
      seller_tax_code: getText(colMap.mst_ban) || '',
      seller_name: getText(colMap.ten_ban) || '',
      amount_untaxed: amountUntaxed,
      amount_tax: amountTax,
      amount_total: amountTotal || (amountUntaxed + amountTax),
      pdf_url: pdfUrl,
      xml_url: xmlUrl,
      pdf_base64: null,
      pdf_filename: null,
      xml_base64: null,
      xml_filename: null,
      pdf_status: pdfUrl ? 'pending' : 'no_link',
    };
  }

  async downloadPdf(invoice) {
    if (!invoice.pdf_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }
    try {
      const response = await fetch(invoice.pdf_url, {
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
      const filename = `shinhan_${invoice.invoice_number}_${new Date().toISOString().split('T')[0]}.pdf`;
      return { pdf_base64: base64, pdf_filename: filename, pdf_status: 'downloaded' };
    } catch (err) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: err.message };
    }
  }

  async downloadXml(invoice) {
    if (!invoice.xml_url) return { xml_base64: null, xml_filename: null };
    try {
      const response = await fetch(invoice.xml_url, { credentials: 'include' });
      if (!response.ok) return { xml_base64: null, xml_filename: null };
      const blob = await response.blob();
      if (blob.size === 0) return { xml_base64: null, xml_filename: null };
      const base64 = await this._blobToBase64(blob);
      return { xml_base64: base64, xml_filename: `shinhan_${invoice.invoice_number}.xml` };
    } catch (err) {
      return { xml_base64: null, xml_filename: null };
    }
  }

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

  _normalizeDate(str) {
    if (!str) return null;
    const trimmed = str.trim();
    const m1 = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (m1) return `${m1[3]}-${m1[2].padStart(2,'0')}-${m1[1].padStart(2,'0')}`;
    const m2 = trimmed.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
    if (m2) return `${m2[3]}-${m2[2].padStart(2,'0')}-${m2[1].padStart(2,'0')}`;
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
    const m3 = trimmed.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m3) return `${m3[3]}-${m3[2].padStart(2,'0')}-${m3[1].padStart(2,'0')}`;
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
  window.ShinhanScraper = ShinhanScraper;
}
