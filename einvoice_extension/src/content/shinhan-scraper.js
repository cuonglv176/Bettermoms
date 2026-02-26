/**
 * shinhan-scraper.js
 * Trích xuất dữ liệu hóa đơn từ einvoice.shinhan.com.vn
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập (Angular app).
 *
 * CHẠY TRONG ISOLATED WORLD (content script context).
 * Giao tiếp với shinhan-interceptor.js (MAIN world) qua CustomEvent.
 *
 * Luồng download PDF/XML:
 * 1. Content script dispatch click event trên link PDF/XML (Angular nhận được vì click event propagate qua cả 2 worlds)
 * 2. Angular xử lý click → gọi API → tạo Blob → tạo <a download> → gọi .click()
 * 3. Interceptor (MAIN world) chặn .click() → capture base64 → dispatch 'ntp-file-intercepted'
 * 4. Content script nhận event → lưu base64 → trả về cho background
 *
 * URL: https://einvoice.shinhan.com.vn/#/invoice-list
 */

class ShinhanScraper {
  constructor() {
    this.source = 'shinhan';
    this._capturedFiles = [];
    this._fileResolvers = [];
    this._setupEventListeners();
  }

  /**
   * Lắng nghe CustomEvent từ main world interceptor.
   */
  _setupEventListeners() {
    window.addEventListener('ntp-file-intercepted', (event) => {
      const fileData = event.detail;
      console.log(`[ShinhanScraper] Received intercepted file: type=${fileData.type}, filename=${fileData.filename}, size=${fileData.base64?.length || 0}`);
      
      this._capturedFiles.push(fileData);
      
      // Resolve pending promise nếu có
      if (this._fileResolvers.length > 0) {
        const resolver = this._fileResolvers.shift();
        resolver(fileData);
      }
    });

    console.log('[ShinhanScraper] Event listeners setup for main world communication');
  }

  /**
   * Đợi file mới từ interceptor.
   */
  _waitForFile(timeout = 15000) {
    return new Promise((resolve) => {
      // Kiểm tra nếu đã có file mới trong queue
      // (interceptor có thể đã capture trước khi ta đợi)
      
      const timer = setTimeout(() => {
        // Timeout - remove resolver
        const idx = this._fileResolvers.indexOf(resolverFn);
        if (idx >= 0) this._fileResolvers.splice(idx, 1);
        resolve(null);
      }, timeout);

      const resolverFn = (fileData) => {
        clearTimeout(timer);
        resolve(fileData);
      };

      this._fileResolvers.push(resolverFn);
    });
  }

  /**
   * Kiểm tra trang đã đăng nhập chưa.
   */
  isLoggedIn() {
    const bodyText = document.body ? document.body.innerText : '';

    const allBtns = document.querySelectorAll('button, a, span');
    for (const el of allBtns) {
      const text = el.textContent.trim().toLowerCase();
      if (text.includes('đăng xuất') || text === 'logout' || text === 'sign out') {
        return true;
      }
    }

    if (bodyText.includes('Chào mừng') || bodyText.includes('quý khách') || bodyText.includes('Đăng xuất')) {
      return true;
    }

    if (window.location.hash.includes('invoice-list') || window.location.hash.includes('invoice')) {
      if (document.querySelector('table')) return true;
    }

    return false;
  }

  /**
   * Lấy danh sách hóa đơn từ bảng HTML trên trang hiện tại.
   */
  scrapeInvoices() {
    const invoices = [];

    const allTables = document.querySelectorAll('table');
    console.log(`[ShinhanScraper] Tổng số bảng: ${allTables.length}`);
    allTables.forEach((t, i) => {
      const ths = Array.from(t.querySelectorAll('th')).map(h => h.textContent.trim());
      const rows = t.querySelectorAll('tbody tr').length;
      console.log(`[ShinhanScraper] Bảng ${i}: ${rows} rows, headers:`, ths);
    });

    if (allTables.length === 0) {
      console.warn('[ShinhanScraper] Không tìm thấy bảng.');
      return invoices;
    }

    let invoiceTable = this._findInvoiceTable(allTables);
    if (!invoiceTable) {
      console.warn('[ShinhanScraper] Không tìm thấy bảng hóa đơn');
      return invoices;
    }

    const headers = Array.from(invoiceTable.querySelectorAll('thead th, th'));
    console.log('[ShinhanScraper] Headers:', headers.map(h => h.textContent.trim()));
    const colMap = this._mapColumns(headers);
    console.log('[ShinhanScraper] Column mapping:', colMap);

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

        const invoice = this._parseRow(cells, colMap, row, index);
        if (invoice && invoice.invoice_number) {
          invoice._id = `shinhan_${index}_${Date.now()}`;
          invoices.push(invoice);
        }
      } catch (err) {
        console.warn(`[ShinhanScraper] Lỗi parse hàng ${index}:`, err.message);
      }
    });

    console.log(`[ShinhanScraper] Kết quả: ${invoices.length} hóa đơn`);
    return invoices;
  }

  _findInvoiceTable(allTables) {
    for (const table of allTables) {
      const headerTexts = Array.from(table.querySelectorAll('th')).map(h => h.textContent.trim().toLowerCase());
      if (headerTexts.some(h => h.includes('số hóa đơn') || h.includes('số hđ') || h.includes('invoice no'))) {
        console.log('[ShinhanScraper] Tìm thấy bảng qua header');
        return table;
      }
    }
    const bsTable = document.querySelector('table.table.table-bordered') ||
                    document.querySelector('table.table-bordered') ||
                    document.querySelector('table.table');
    if (bsTable) {
      console.log('[ShinhanScraper] Tìm thấy bảng qua class Bootstrap');
      return bsTable;
    }
    let maxCols = 0, best = null;
    for (const table of allTables) {
      const colCount = table.querySelectorAll('th').length;
      if (colCount > maxCols) { maxCols = colCount; best = table; }
    }
    if (best) console.log(`[ShinhanScraper] Fallback: bảng ${maxCols} cột`);
    return best;
  }

  _mapColumns(headers) {
    const map = {
      stt: -1, loai_hd: -1, mst_ban: -1, ten_ban: -1, ky_hieu: -1,
      so_hd: -1, ngay_hd: -1, ten_hang: -1, loai_tien: -1, ty_gia: -1,
      cong_tien: -1, thue_suat: -1, tien_thue: -1, tong_cong: -1,
      tai_ve: -1, thao_tac: -1,
    };

    headers.forEach((th, idx) => {
      const text = th.textContent.trim().toLowerCase();
      if (text === 'stt' || text === '#') map.stt = idx;
      else if (text.includes('loại hóa đơn') || text.includes('loại hđ')) map.loai_hd = idx;
      else if ((text.includes('mã số thuế') || text.includes('mst')) && text.includes('bán')) map.mst_ban = idx;
      else if (text.includes('tên người bán') || (text.includes('tên') && text.includes('bán'))) map.ten_ban = idx;
      else if (text.includes('ký hiệu') || text.includes('kí hiệu')) map.ky_hieu = idx;
      else if (text.includes('số hóa đơn') || text.includes('số hđ') || text.includes('invoice no')) map.so_hd = idx;
      else if (text.includes('ngày hóa đơn') || text.includes('ngày hđ')) map.ngay_hd = idx;
      else if (text.includes('tên hàng') || text.includes('dịch vụ')) map.ten_hang = idx;
      else if (text.includes('loại tiền') && !text.includes('cộng')) map.loai_tien = idx;
      else if (text.includes('tỷ giá')) map.ty_gia = idx;
      else if (text.includes('cộng tiền') || text.includes('tiền hàng')) map.cong_tien = idx;
      else if (text.includes('thuế suất')) map.thue_suat = idx;
      else if (text.includes('tiền thuế')) map.tien_thue = idx;
      else if (text.includes('tổng cộng') || text.includes('thanh toán')) map.tong_cong = idx;
      else if (text.includes('tải về') || text.includes('download')) map.tai_ve = idx;
      else if (text.includes('thao tác') || text.includes('action')) map.thao_tac = idx;
    });

    if (map.so_hd === -1 && headers.length >= 14) {
      console.log('[ShinhanScraper] Dùng fallback cứng 16 cột');
      map.stt = 0; map.loai_hd = 1; map.mst_ban = 2; map.ten_ban = 3;
      map.ky_hieu = 4; map.so_hd = 5; map.ngay_hd = 6; map.ten_hang = 7;
      map.loai_tien = 8; map.ty_gia = 9; map.cong_tien = 10; map.thue_suat = 11;
      map.tien_thue = 12; map.tong_cong = 13;
      if (headers.length >= 15) map.tai_ve = 14;
      if (headers.length >= 16) map.thao_tac = 15;
    }

    return map;
  }

  _parseRow(cells, colMap, row, rowIndex) {
    const getText = (idx) => {
      if (idx < 0 || idx >= cells.length) return '';
      return cells[idx].textContent.trim();
    };

    let invoiceNumber = getText(colMap.so_hd);

    if (!invoiceNumber) {
      for (let i = 0; i < cells.length; i++) {
        const text = cells[i].textContent.trim();
        if (/^\d{4,12}$/.test(text)) {
          invoiceNumber = text;
          break;
        }
      }
    }

    if (!invoiceNumber) return null;

    // Tìm link PDF/XML trong row
    let hasPdfLink = false;
    let hasXmlLink = false;

    if (colMap.tai_ve >= 0 && colMap.tai_ve < cells.length) {
      const links = cells[colMap.tai_ve].querySelectorAll('a');
      links.forEach(link => {
        const linkText = link.textContent.trim().toUpperCase();
        if (linkText === 'PDF' || linkText.includes('PDF')) hasPdfLink = true;
        if (linkText === 'XML' || linkText.includes('XML')) hasXmlLink = true;
      });
    }

    if (!hasPdfLink || !hasXmlLink) {
      const allLinks = row.querySelectorAll('a');
      allLinks.forEach(link => {
        const text = link.textContent.trim().toUpperCase();
        if (!hasPdfLink && (text === 'PDF' || text.includes('PDF'))) hasPdfLink = true;
        if (!hasXmlLink && (text === 'XML' || text.includes('XML'))) hasXmlLink = true;
      });
    }

    console.log(`[ShinhanScraper] Row ${rowIndex}: HĐ=${invoiceNumber}, PDF=${hasPdfLink}, XML=${hasXmlLink}`);

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
      _rowIndex: rowIndex,
      _hasPdfLink: hasPdfLink,
      _hasXmlLink: hasXmlLink,
      pdf_url: hasPdfLink ? `shinhan_click_pdf_row_${rowIndex}` : null,
      xml_url: hasXmlLink ? `shinhan_click_xml_row_${rowIndex}` : null,
      pdf_base64: null,
      pdf_filename: null,
      xml_base64: null,
      xml_filename: null,
      pdf_status: hasPdfLink ? 'pending' : 'no_link',
    };
  }

  /**
   * Download PDF cho một hóa đơn bằng cách click vào link PDF trên bảng.
   * Interceptor (main world) sẽ chặn download và gửi base64 qua CustomEvent.
   */
  async downloadPdf(invoice) {
    if (!invoice._hasPdfLink && !invoice.pdf_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }

    try {
      console.log(`[ShinhanScraper] Download PDF cho HĐ ${invoice.invoice_number} (row ${invoice._rowIndex})`);

      // Xóa cache cũ
      window.dispatchEvent(new CustomEvent('ntp-clear-intercepted'));
      this._capturedFiles = [];

      // Bắt đầu đợi file từ interceptor
      const filePromise = this._waitForFile(15000);

      // Tìm link PDF trong DOM và click
      const pdfLink = this._findLinkInRow(invoice._rowIndex, 'PDF');
      if (!pdfLink) {
        console.warn(`[ShinhanScraper] Không tìm thấy link PDF cho row ${invoice._rowIndex}`);
        return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: 'Không tìm thấy link PDF' };
      }

      // Click link - event sẽ propagate qua cả isolated và main world
      // Angular (main world) sẽ xử lý click → download → interceptor chặn
      console.log(`[ShinhanScraper] Clicking PDF link for row ${invoice._rowIndex}...`);
      pdfLink.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
      }));

      // Đợi interceptor capture file
      const result = await filePromise;

      if (result && result.base64) {
        const filename = result.filename || `shinhan_${invoice.invoice_number}.pdf`;
        console.log(`[ShinhanScraper] PDF captured: ${invoice.invoice_number}, size=${result.base64.length}`);
        return { pdf_base64: result.base64, pdf_filename: filename, pdf_status: 'downloaded' };
      }

      console.warn(`[ShinhanScraper] Không capture được PDF cho ${invoice.invoice_number} sau 15s`);
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: 'Interceptor timeout' };
    } catch (err) {
      console.error(`[ShinhanScraper] Lỗi download PDF ${invoice.invoice_number}:`, err);
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: err.message };
    }
  }

  /**
   * Download XML cho một hóa đơn.
   */
  async downloadXml(invoice) {
    if (!invoice._hasXmlLink && !invoice.xml_url) {
      return { xml_base64: null, xml_filename: null };
    }

    try {
      console.log(`[ShinhanScraper] Download XML cho HĐ ${invoice.invoice_number} (row ${invoice._rowIndex})`);

      // Xóa cache cũ
      window.dispatchEvent(new CustomEvent('ntp-clear-intercepted'));
      this._capturedFiles = [];

      const filePromise = this._waitForFile(15000);

      const xmlLink = this._findLinkInRow(invoice._rowIndex, 'XML');
      if (!xmlLink) {
        return { xml_base64: null, xml_filename: null };
      }

      xmlLink.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
      }));

      const result = await filePromise;

      if (result && result.base64) {
        const filename = result.filename || `shinhan_${invoice.invoice_number}.xml`;
        console.log(`[ShinhanScraper] XML captured: ${invoice.invoice_number}`);
        return { xml_base64: result.base64, xml_filename: filename };
      }

      return { xml_base64: null, xml_filename: null };
    } catch (err) {
      console.warn(`[ShinhanScraper] Lỗi download XML ${invoice.invoice_number}:`, err);
      return { xml_base64: null, xml_filename: null };
    }
  }

  /**
   * Tìm link (PDF hoặc XML) trong row theo index.
   */
  _findLinkInRow(rowIndex, linkType) {
    const table = this._findInvoiceTable(document.querySelectorAll('table'));
    if (!table) return null;
    const rows = table.querySelectorAll('tbody tr');
    if (rowIndex >= rows.length) return null;
    const row = rows[rowIndex];
    const links = row.querySelectorAll('a');
    for (const link of links) {
      if (link.textContent.trim().toUpperCase().includes(linkType)) return link;
    }
    return null;
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
    if (m1) return `${m1[3]}-${m1[2].padStart(2, '0')}-${m1[1].padStart(2, '0')}`;
    const m2 = trimmed.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
    if (m2) return `${m2[3]}-${m2[2].padStart(2, '0')}-${m2[1].padStart(2, '0')}`;
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
    const m3 = trimmed.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m3) return `${m3[3]}-${m3[2].padStart(2, '0')}-${m3[1].padStart(2, '0')}`;
    return null;
  }
}

if (typeof window !== 'undefined') {
  window.ShinhanScraper = ShinhanScraper;
}
