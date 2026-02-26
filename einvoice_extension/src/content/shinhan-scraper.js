/**
 * shinhan-scraper.js
 * Trích xuất dữ liệu hóa đơn từ einvoice.shinhan.com.vn
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập.
 *
 * Cấu trúc bảng (từ phân tích thực tế - Angular 7 app):
 * table.table.table-bordered
 * Headers (16 cột):
 *   0: STT
 *   1: Loại hóa đơn
 *   2: Mã số thuế người bán
 *   3: Tên người bán
 *   4: Ký hiệu
 *   5: Số hóa đơn
 *   6: Ngày hóa đơn
 *   7: Tên hàng hóa, dịch vụ
 *   8: Loại tiền
 *   9: Tỷ giá
 *   10: Cộng tiền hàng hóa, dịch vụ
 *   11: Thuế suất thuế GTGT
 *   12: Tiền thuế GTGT
 *   13: Tổng cộng thanh toán
 *   14: Tải về (XML | PDF links)
 *   15: Thao tác (Xem icon)
 */

/**
 * ShinhanScraper - Scrape hóa đơn trực tiếp từ DOM trang Shinhan.
 * Chạy trong context của content script.
 */
class ShinhanScraper {
  constructor() {
    this.source = 'shinhan';
  }

  /**
   * Kiểm tra trang đã đăng nhập chưa.
   */
  isLoggedIn() {
    // Kiểm tra nút "Đăng xuất" có hiển thị không
    const logoutBtn = document.querySelector('button, a');
    const allButtons = document.querySelectorAll('button, a');
    for (const btn of allButtons) {
      const text = btn.textContent.trim().toLowerCase();
      if (text.includes('đăng xuất') || text.includes('logout') || text.includes('sign out')) {
        return true;
      }
    }
    // Kiểm tra có text "Chào mừng" không
    const bodyText = document.body.innerText || '';
    if (bodyText.includes('Chào mừng') || bodyText.includes('quý khách')) {
      return true;
    }
    return false;
  }

  /**
   * Lấy danh sách hóa đơn từ bảng HTML trên trang hiện tại.
   * @returns {Array} Danh sách hóa đơn
   */
  scrapeInvoices() {
    const invoices = [];

    // Tìm bảng chính (table.table.table-bordered)
    let invoiceTable = document.querySelector('table.table.table-bordered');

    if (!invoiceTable) {
      // Fallback: tìm bảng có nhiều cột nhất
      const tables = document.querySelectorAll('table');
      let maxCols = 0;
      for (const table of tables) {
        const headers = table.querySelectorAll('th');
        if (headers.length > maxCols) {
          maxCols = headers.length;
          invoiceTable = table;
        }
      }
    }

    if (!invoiceTable) {
      console.warn('[ShinhanScraper] Không tìm thấy bảng hóa đơn');
      return invoices;
    }

    // Xác định vị trí các cột dựa trên header
    const headers = Array.from(invoiceTable.querySelectorAll('thead th, th'));
    const colMap = this._mapColumns(headers);

    console.log('[ShinhanScraper] Column mapping:', colMap);

    // Lấy dữ liệu từ các hàng
    const rows = invoiceTable.querySelectorAll('tbody tr');
    console.log(`[ShinhanScraper] Tìm thấy ${rows.length} hàng trong bảng`);

    rows.forEach((row, index) => {
      try {
        const cells = row.querySelectorAll('td');
        if (cells.length < 5) return; // Bỏ qua hàng quá ngắn

        const invoice = this._parseRow(cells, colMap, row);
        if (invoice && invoice.invoice_number) {
          invoice._id = `shinhan_${index}_${Date.now()}`;
          invoices.push(invoice);
        }
      } catch (err) {
        console.warn(`[ShinhanScraper] Lỗi parse hàng ${index}:`, err);
      }
    });

    console.log(`[ShinhanScraper] Scrape được ${invoices.length} hóa đơn`);
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
      } else if (text.includes('loại hóa đơn') || text.includes('loại hđ')) {
        map.loai_hd = idx;
      } else if (text.includes('mã số thuế') && text.includes('bán')) {
        map.mst_ban = idx;
      } else if (text.includes('tên người bán') || text.includes('tên ncc')) {
        map.ten_ban = idx;
      } else if (text.includes('ký hiệu') || text.includes('serial')) {
        map.ky_hieu = idx;
      } else if (text.includes('số hóa đơn') || text.includes('số hđ')) {
        map.so_hd = idx;
      } else if (text.includes('ngày hóa đơn') || text.includes('ngày hđ')) {
        map.ngay_hd = idx;
      } else if (text.includes('tên hàng') || text.includes('dịch vụ')) {
        map.ten_hang = idx;
      } else if (text.includes('loại tiền') && !text.includes('cộng')) {
        map.loai_tien = idx;
      } else if (text.includes('tỷ giá')) {
        map.ty_gia = idx;
      } else if (text.includes('cộng tiền') || text.includes('tiền hàng')) {
        map.cong_tien = idx;
      } else if (text.includes('thuế suất')) {
        map.thue_suat = idx;
      } else if (text.includes('tiền thuế')) {
        map.tien_thue = idx;
      } else if (text.includes('tổng cộng') || text.includes('thanh toán')) {
        map.tong_cong = idx;
      } else if (text.includes('tải về') || text.includes('download')) {
        map.tai_ve = idx;
      } else if (text.includes('thao tác') || text.includes('action')) {
        map.thao_tac = idx;
      }
    });

    // Fallback cho bảng Shinhan chuẩn 16 cột
    if (map.so_hd === -1 && headers.length >= 14) {
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

    const invoiceNumber = getText(colMap.so_hd);
    if (!invoiceNumber) return null;

    // Lấy link PDF và XML từ cột "Tải về"
    let pdfUrl = null;
    let xmlUrl = null;
    if (colMap.tai_ve >= 0 && colMap.tai_ve < cells.length) {
      const links = cells[colMap.tai_ve].querySelectorAll('a');
      links.forEach(link => {
        const linkText = link.textContent.trim().toUpperCase();
        const href = link.href || link.getAttribute('href') || '';
        const onclick = link.getAttribute('onclick') || '';
        if (linkText.includes('PDF') || href.includes('pdf')) {
          pdfUrl = href || onclick;
        }
        if (linkText.includes('XML') || href.includes('xml')) {
          xmlUrl = href || onclick;
        }
      });
    }

    // Cũng tìm link trong toàn bộ hàng
    if (!pdfUrl || !xmlUrl) {
      const allLinks = row.querySelectorAll('a');
      allLinks.forEach(link => {
        const text = link.textContent.trim().toUpperCase();
        const href = link.href || link.getAttribute('href') || '';
        if (!pdfUrl && (text === 'PDF' || href.includes('pdf'))) {
          pdfUrl = href;
        }
        if (!xmlUrl && (text === 'XML' || href.includes('xml'))) {
          xmlUrl = href;
        }
      });
    }

    // Parse số tiền
    const amountUntaxed = this._parseAmount(getText(colMap.cong_tien));
    const amountTax = this._parseAmount(getText(colMap.tien_thue));
    const amountTotal = this._parseAmount(getText(colMap.tong_cong));

    // Parse ngày
    const dateStr = getText(colMap.ngay_hd);
    const normalizedDate = this._normalizeDate(dateStr);

    return {
      source: 'shinhan',
      invoice_number: invoiceNumber,
      invoice_code: '',
      invoice_symbol: getText(colMap.ky_hieu),
      invoice_date: normalizedDate,
      seller_tax_code: getText(colMap.mst_ban),
      seller_name: getText(colMap.ten_ban),
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
      const filename = `shinhan_${invoice.invoice_number}_${new Date().toISOString().split('T')[0]}.pdf`;

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
   * Tải XML cho một hóa đơn.
   */
  async downloadXml(invoice) {
    if (!invoice.xml_url) {
      return { xml_base64: null, xml_filename: null };
    }

    try {
      const response = await fetch(invoice.xml_url, {
        credentials: 'include',
      });

      if (!response.ok) return { xml_base64: null, xml_filename: null };

      const blob = await response.blob();
      if (blob.size === 0) return { xml_base64: null, xml_filename: null };

      const base64 = await this._blobToBase64(blob);
      const filename = `shinhan_${invoice.invoice_number}.xml`;

      return { xml_base64: base64, xml_filename: filename };
    } catch (err) {
      return { xml_base64: null, xml_filename: null };
    }
  }

  /**
   * Parse số tiền từ chuỗi hiển thị.
   */
  _parseAmount(str) {
    if (!str) return 0;
    // Shinhan hiển thị số dạng: 9,000.00 hoặc 9.000,00
    // Detect format: nếu có dấu phẩy trước dấu chấm cuối → English format (9,000.00)
    // Nếu có dấu chấm trước dấu phẩy cuối → VN format (9.000,00)
    const cleaned = str.replace(/[^\d.,]/g, '');
    if (!cleaned) return 0;

    const lastComma = cleaned.lastIndexOf(',');
    const lastDot = cleaned.lastIndexOf('.');

    let result;
    if (lastComma > lastDot) {
      // VN format: 9.000,00 → replace . with nothing, , with .
      result = cleaned.replace(/\./g, '').replace(',', '.');
    } else {
      // English format: 9,000.00 → replace , with nothing
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

    // DD/MM/YYYY
    const m1 = trimmed.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m1) return `${m1[3]}-${m1[2]}-${m1[1]}`;

    // DD-MM-YYYY
    const m2 = trimmed.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (m2) return `${m2[3]}-${m2[2]}-${m2[1]}`;

    // YYYY-MM-DD
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;

    // DD.MM.YYYY
    const m3 = trimmed.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (m3) return `${m3[3]}-${m3[2]}-${m3[1]}`;

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
  window.ShinhanScraper = ShinhanScraper;
}
