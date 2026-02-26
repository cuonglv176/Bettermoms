/**
 * shinhan-scraper.js
 * Trích xuất dữ liệu hóa đơn từ einvoice.shinhan.com.vn
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập (Angular app).
 *
 * Bảng đầy đủ (16 cột):
 * STT | Loại HĐ | MST người bán | Tên người bán | Ký hiệu | Số HĐ | Ngày HĐ | Tên hàng | Loại tiền | Tỷ giá | Cộng tiền | Thuế suất | Tiền thuế | Tổng cộng | Tải về | Thao tác
 *  0  |    1    |       2       |      3        |    4    |   5   |    6    |    7     |     8     |    9   |    10     |    11     |    12     |    13     |   14   |    15
 *
 * QUAN TRỌNG: Link PDF/XML trên Shinhan KHÔNG có href.
 * Angular xử lý click event. Cần dùng click simulation + intercept XHR/fetch.
 *
 * URL: https://einvoice.shinhan.com.vn/#/invoice-list
 */

class ShinhanScraper {
  constructor() {
    this.source = 'shinhan';
    this._interceptedFiles = {};
    this._setupInterceptor();
  }

  /**
   * Setup XHR/Fetch interceptor để bắt file PDF/XML khi Angular download.
   * Khi click vào link PDF/XML, Angular sẽ gọi API → interceptor bắt response.
   */
  _setupInterceptor() {
    const self = this;

    // Intercept XMLHttpRequest
    const origXHROpen = XMLHttpRequest.prototype.open;
    const origXHRSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url, ...args) {
      this._ntpUrl = url;
      this._ntpMethod = method;
      return origXHROpen.call(this, method, url, ...args);
    };

    XMLHttpRequest.prototype.send = function(body) {
      const xhr = this;
      const url = xhr._ntpUrl || '';

      // Detect PDF/XML download requests
      if (url && (url.includes('pdf') || url.includes('xml') || url.includes('download') ||
                  url.includes('invoice') || url.includes('hoadon'))) {
        xhr.addEventListener('load', function() {
          try {
            const contentType = xhr.getResponseHeader('content-type') || '';
            const responseUrl = xhr.responseURL || url;

            if (contentType.includes('application/pdf') ||
                contentType.includes('application/octet-stream') ||
                contentType.includes('text/xml') ||
                contentType.includes('application/xml')) {

              const fileType = (contentType.includes('xml') || url.includes('xml')) ? 'xml' : 'pdf';
              const key = `${fileType}_${Date.now()}`;

              console.log(`[ShinhanScraper] Intercepted ${fileType}: ${responseUrl}, type: ${contentType}, size: ${xhr.response?.byteLength || xhr.response?.size || 'unknown'}`);

              // Lưu response
              self._interceptedFiles[key] = {
                type: fileType,
                url: responseUrl,
                contentType: contentType,
                response: xhr.response,
                timestamp: Date.now(),
              };
            }
          } catch (e) {
            console.warn('[ShinhanScraper] Interceptor error:', e);
          }
        });

        // Đảm bảo response type là arraybuffer để đọc binary
        if (!xhr.responseType || xhr.responseType === '') {
          xhr.responseType = 'arraybuffer';
        }
      }

      return origXHRSend.call(this, body);
    };

    // Intercept fetch
    const origFetch = window.fetch;
    window.fetch = function(input, init) {
      const url = typeof input === 'string' ? input : input?.url || '';

      return origFetch.call(this, input, init).then(response => {
        if (url && (url.includes('pdf') || url.includes('xml') || url.includes('download'))) {
          const contentType = response.headers.get('content-type') || '';
          if (contentType.includes('application/pdf') ||
              contentType.includes('application/octet-stream') ||
              contentType.includes('text/xml') ||
              contentType.includes('application/xml')) {

            const fileType = (contentType.includes('xml') || url.includes('xml')) ? 'xml' : 'pdf';
            console.log(`[ShinhanScraper] Fetch intercepted ${fileType}: ${url}`);

            // Clone response để không ảnh hưởng Angular
            const cloned = response.clone();
            cloned.arrayBuffer().then(buffer => {
              self._interceptedFiles[`${fileType}_${Date.now()}`] = {
                type: fileType,
                url: url,
                contentType: contentType,
                buffer: buffer,
                timestamp: Date.now(),
              };
            }).catch(() => {});
          }
        }
        return response;
      });
    };

    console.log('[ShinhanScraper] XHR/Fetch interceptor installed');
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

    // Tìm bảng chứa hóa đơn
    let invoiceTable = this._findInvoiceTable(allTables);
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
    // Ưu tiên 1: header "Số hóa đơn"
    for (const table of allTables) {
      const headerTexts = Array.from(table.querySelectorAll('th')).map(h => h.textContent.trim().toLowerCase());
      if (headerTexts.some(h => h.includes('số hóa đơn') || h.includes('số hđ') || h.includes('invoice no'))) {
        console.log('[ShinhanScraper] Tìm thấy bảng qua header');
        return table;
      }
    }
    // Ưu tiên 2: Bootstrap class
    const bsTable = document.querySelector('table.table.table-bordered') ||
                    document.querySelector('table.table-bordered') ||
                    document.querySelector('table.table');
    if (bsTable) {
      console.log('[ShinhanScraper] Tìm thấy bảng qua class Bootstrap');
      return bsTable;
    }
    // Ưu tiên 3: Bảng nhiều cột nhất
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

    // Fallback cứng cho bảng Shinhan 16 cột
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

    // Fallback: tìm cell có dạng số hóa đơn (chỉ số, 4-12 ký tự)
    if (!invoiceNumber) {
      for (let i = 0; i < cells.length; i++) {
        const text = cells[i].textContent.trim();
        if (/^\d{4,12}$/.test(text)) {
          invoiceNumber = text;
          break;
        }
      }
    }

    // Fallback: tìm cell có pattern F + số hoặc chỉ số
    if (!invoiceNumber) {
      for (let i = 0; i < cells.length; i++) {
        const text = cells[i].textContent.trim();
        if (/^[A-Z]?\d{3,12}$/.test(text)) {
          invoiceNumber = text;
          break;
        }
      }
    }

    if (!invoiceNumber) return null;

    // Lưu reference đến các link PDF/XML trong row (dùng cho click simulation)
    let pdfLink = null;
    let xmlLink = null;

    // Tìm link PDF/XML trong cột "Tải về"
    if (colMap.tai_ve >= 0 && colMap.tai_ve < cells.length) {
      const links = cells[colMap.tai_ve].querySelectorAll('a');
      links.forEach(link => {
        const linkText = link.textContent.trim().toUpperCase();
        if (linkText === 'PDF' || linkText.includes('PDF')) pdfLink = link;
        if (linkText === 'XML' || linkText.includes('XML')) xmlLink = link;
      });
    }

    // Tìm trong toàn bộ hàng
    if (!pdfLink || !xmlLink) {
      const allLinks = row.querySelectorAll('a');
      allLinks.forEach(link => {
        const text = link.textContent.trim().toUpperCase();
        if (!pdfLink && (text === 'PDF' || text.includes('PDF'))) pdfLink = link;
        if (!xmlLink && (text === 'XML' || text.includes('XML'))) xmlLink = link;
      });
    }

    const hasPdfLink = !!pdfLink;
    const hasXmlLink = !!xmlLink;

    console.log(`[ShinhanScraper] Row ${rowIndex}: HĐ=${invoiceNumber}, PDF link=${hasPdfLink}, XML link=${hasXmlLink}`);

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
      // Lưu row index để tìm lại link khi download
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
   * Interceptor sẽ bắt response và lưu lại.
   */
  async downloadPdf(invoice) {
    if (!invoice._hasPdfLink && !invoice.pdf_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }

    try {
      console.log(`[ShinhanScraper] Download PDF cho HĐ ${invoice.invoice_number} (row ${invoice._rowIndex})`);

      // Clear intercepted files trước khi click
      const beforeKeys = Object.keys(this._interceptedFiles);

      // Tìm lại link PDF trong DOM
      const pdfLink = this._findPdfLinkInRow(invoice._rowIndex);
      if (!pdfLink) {
        console.warn(`[ShinhanScraper] Không tìm thấy link PDF cho row ${invoice._rowIndex}`);
        return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: 'Không tìm thấy link PDF' };
      }

      // Click vào link PDF
      console.log(`[ShinhanScraper] Clicking PDF link for row ${invoice._rowIndex}...`);
      pdfLink.click();

      // Đợi interceptor bắt được response (tối đa 10 giây)
      const result = await this._waitForInterceptedFile('pdf', beforeKeys, 10000);

      if (result) {
        const base64 = await this._arrayBufferToBase64(result.response || result.buffer);
        const filename = `shinhan_${invoice.invoice_number}_${new Date().toISOString().split('T')[0]}.pdf`;
        console.log(`[ShinhanScraper] PDF downloaded: ${invoice.invoice_number}, size=${base64.length}`);
        return { pdf_base64: base64, pdf_filename: filename, pdf_status: 'downloaded' };
      }

      // Fallback: Nếu interceptor không bắt được, thử dùng Blob URL
      console.warn(`[ShinhanScraper] Interceptor không bắt được PDF cho ${invoice.invoice_number}`);
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: 'Interceptor timeout' };
    } catch (err) {
      console.error(`[ShinhanScraper] Lỗi download PDF ${invoice.invoice_number}:`, err);
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: err.message };
    }
  }

  /**
   * Download XML cho một hóa đơn bằng cách click vào link XML trên bảng.
   */
  async downloadXml(invoice) {
    if (!invoice._hasXmlLink && !invoice.xml_url) {
      return { xml_base64: null, xml_filename: null };
    }

    try {
      console.log(`[ShinhanScraper] Download XML cho HĐ ${invoice.invoice_number} (row ${invoice._rowIndex})`);

      const beforeKeys = Object.keys(this._interceptedFiles);

      const xmlLink = this._findXmlLinkInRow(invoice._rowIndex);
      if (!xmlLink) {
        return { xml_base64: null, xml_filename: null };
      }

      xmlLink.click();

      const result = await this._waitForInterceptedFile('xml', beforeKeys, 10000);

      if (result) {
        const base64 = await this._arrayBufferToBase64(result.response || result.buffer);
        const filename = `shinhan_${invoice.invoice_number}.xml`;
        console.log(`[ShinhanScraper] XML downloaded: ${invoice.invoice_number}`);
        return { xml_base64: base64, xml_filename: filename };
      }

      return { xml_base64: null, xml_filename: null };
    } catch (err) {
      console.warn(`[ShinhanScraper] Lỗi download XML ${invoice.invoice_number}:`, err);
      return { xml_base64: null, xml_filename: null };
    }
  }

  /**
   * Tìm link PDF trong row theo index.
   */
  _findPdfLinkInRow(rowIndex) {
    const table = this._findInvoiceTable(document.querySelectorAll('table'));
    if (!table) return null;
    const rows = table.querySelectorAll('tbody tr');
    if (rowIndex >= rows.length) return null;
    const row = rows[rowIndex];
    const links = row.querySelectorAll('a');
    for (const link of links) {
      if (link.textContent.trim().toUpperCase().includes('PDF')) return link;
    }
    return null;
  }

  /**
   * Tìm link XML trong row theo index.
   */
  _findXmlLinkInRow(rowIndex) {
    const table = this._findInvoiceTable(document.querySelectorAll('table'));
    if (!table) return null;
    const rows = table.querySelectorAll('tbody tr');
    if (rowIndex >= rows.length) return null;
    const row = rows[rowIndex];
    const links = row.querySelectorAll('a');
    for (const link of links) {
      if (link.textContent.trim().toUpperCase().includes('XML')) return link;
    }
    return null;
  }

  /**
   * Đợi interceptor bắt được file mới.
   */
  _waitForInterceptedFile(fileType, beforeKeys, timeout = 10000) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const interval = setInterval(() => {
        const currentKeys = Object.keys(this._interceptedFiles);
        const newKeys = currentKeys.filter(k => !beforeKeys.includes(k) && k.startsWith(fileType));

        if (newKeys.length > 0) {
          clearInterval(interval);
          const latestKey = newKeys[newKeys.length - 1];
          resolve(this._interceptedFiles[latestKey]);
          // Cleanup
          delete this._interceptedFiles[latestKey];
        } else if (Date.now() - startTime > timeout) {
          clearInterval(interval);
          resolve(null);
        }
      }, 200);
    });
  }

  /**
   * Convert ArrayBuffer to Base64.
   */
  _arrayBufferToBase64(buffer) {
    return new Promise((resolve) => {
      if (buffer instanceof ArrayBuffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        resolve(btoa(binary));
      } else if (buffer instanceof Blob) {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.readAsDataURL(buffer);
      } else {
        resolve(null);
      }
    });
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
