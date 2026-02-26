/**
 * shinhan-scraper.js
 * Trích xuất dữ liệu hóa đơn từ einvoice.shinhan.com.vn
 * Đọc trực tiếp DOM bảng HTML trên trang đã đăng nhập (Angular app).
 *
 * Bảng đầy đủ (16 cột):
 * STT | Loại HĐ | MST người bán | Tên người bán | Ký hiệu | Số HĐ | Ngày HĐ | Tên hàng | Loại tiền | Tỷ giá | Cộng tiền | Thuế suất | Tiền thuế | Tổng cộng | Tải về | Thao tác
 *
 * QUAN TRỌNG: Link PDF/XML trên Shinhan KHÔNG có href.
 * Angular xử lý click event → gọi API → tạo Blob → tạo <a download> ẩn → click.
 * Cần intercept toàn bộ chuỗi này để capture file data thay vì download về máy.
 *
 * URL: https://einvoice.shinhan.com.vn/#/invoice-list
 */

class ShinhanScraper {
  constructor() {
    this.source = 'shinhan';
    this._interceptedFiles = [];
    this._isInterceptorReady = false;
    this._setupInterceptor();
  }

  /**
   * Setup interceptor toàn diện để bắt file PDF/XML khi Angular download.
   *
   * Angular download flow:
   * 1. Click link → Angular service gọi HTTP API (XHR hoặc fetch)
   * 2. Nhận response (ArrayBuffer/Blob)
   * 3. Tạo Blob URL: URL.createObjectURL(blob)
   * 4. Tạo <a href="blob:..." download="filename"> ẩn
   * 5. Gọi a.click() → browser download file
   *
   * Ta intercept ở nhiều điểm để đảm bảo bắt được file.
   */
  _setupInterceptor() {
    const self = this;

    // ============================================================
    // Interceptor 1: Override URL.createObjectURL
    // Bắt khi Angular tạo Blob URL cho download
    // ============================================================
    const origCreateObjectURL = URL.createObjectURL.bind(URL);
    URL.createObjectURL = function (obj) {
      const blobUrl = origCreateObjectURL(obj);

      if (obj instanceof Blob && obj.size > 100) {
        const type = obj.type || '';
        console.log(`[ShinhanScraper] Blob URL created: type="${type}", size=${obj.size}, url=${blobUrl}`);

        // Đọc blob data ngay lập tức
        const reader = new FileReader();
        reader.onload = function () {
          const base64 = reader.result.split(',')[1];
          const fileType = (type.includes('xml') || type.includes('text/xml')) ? 'xml' : 'pdf';
          console.log(`[ShinhanScraper] Captured ${fileType} from Blob: size=${base64.length}`);
          self._interceptedFiles.push({
            type: fileType,
            base64: base64,
            blobUrl: blobUrl,
            size: obj.size,
            contentType: type,
            timestamp: Date.now(),
            filename: null, // Sẽ được set bởi interceptor <a download>
          });
        };
        reader.readAsDataURL(obj);
      }

      return blobUrl;
    };

    // ============================================================
    // Interceptor 2: Override HTMLAnchorElement.prototype.click
    // Bắt TẤT CẢ <a>.click() - kể cả element tạo trước interceptor
    // Đây là cách chắc chắn nhất vì Angular luôn gọi .click()
    // ============================================================
    const origAnchorClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
      const href = this.href || '';
      const download = this.download || this.getAttribute('download') || '';

      if (href.startsWith('blob:') && download) {
        console.log(`[ShinhanScraper] Intercepted <a>.click(): download="${download}", href="${href}"`);

        // Tìm file đã capture từ Blob URL
        const captured = self._interceptedFiles.find(f => f.blobUrl === href);
        if (captured) {
          captured.filename = download;
          // Xác định type từ filename nếu chưa rõ
          if (download.toLowerCase().endsWith('.xml')) {
            captured.type = 'xml';
          } else if (download.toLowerCase().endsWith('.pdf')) {
            captured.type = 'pdf';
          }
          console.log(`[ShinhanScraper] Matched: "${download}" → ${captured.type}, base64 size=${captured.base64?.length || 0}`);
        } else {
          console.warn(`[ShinhanScraper] Blob URL not found in intercepted files: ${href}`);
          // Fallback: đọc blob từ URL
          fetch(href).then(r => r.blob()).then(blob => {
            const reader = new FileReader();
            reader.onload = function () {
              const base64 = reader.result.split(',')[1];
              const fileType = download.toLowerCase().endsWith('.xml') ? 'xml' : 'pdf';
              self._interceptedFiles.push({
                type: fileType,
                base64: base64,
                blobUrl: href,
                size: blob.size,
                filename: download,
                timestamp: Date.now(),
              });
              console.log(`[ShinhanScraper] Fallback captured: "${download}" → ${fileType}`);
            };
            reader.readAsDataURL(blob);
          }).catch(e => console.warn('[ShinhanScraper] Fallback fetch failed:', e));
        }

        // KHÔNG gọi click gốc → ngăn download về máy
        // Cleanup blob URL sau 2 giây
        setTimeout(() => {
          try { URL.revokeObjectURL(href); } catch (e) { /* ignore */ }
        }, 2000);
        return;
      }

      // Cho các link bình thường, gọi click gốc
      return origAnchorClick.call(this);
    };

    // ============================================================
    // Interceptor 3: MutationObserver - bắt <a download> khi thêm vào DOM
    // Backup cho trường hợp Angular append element vào body trước khi click
    // ============================================================
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.tagName === 'A' && node.download && node.href && node.href.startsWith('blob:')) {
            console.log(`[ShinhanScraper] MutationObserver: <a download="${node.download}"> added to DOM`);
            // File đã được capture bởi Interceptor 1 (createObjectURL)
            // Chỉ cần set filename
            const captured = self._interceptedFiles.find(f => f.blobUrl === node.href);
            if (captured && !captured.filename) {
              captured.filename = node.download;
            }
          }
        }
      }
    });

    observer.observe(document.body || document.documentElement, {
      childList: true,
      subtree: true,
    });

    // ============================================================
    // Interceptor 4: Override window.open (nếu Angular mở tab mới)
    // ============================================================
    const origWindowOpen = window.open;
    window.open = function (url, ...args) {
      if (url && url.startsWith('blob:')) {
        console.log(`[ShinhanScraper] Intercepted window.open(blob:...)`);
        // Không mở tab mới, đọc blob thay thế
        fetch(url).then(r => r.blob()).then(blob => {
          const reader = new FileReader();
          reader.onload = function () {
            const base64 = reader.result.split(',')[1];
            self._interceptedFiles.push({
              type: 'pdf',
              base64: base64,
              blobUrl: url,
              size: blob.size,
              timestamp: Date.now(),
            });
          };
          reader.readAsDataURL(blob);
        }).catch(() => {});
        return null;
      }
      return origWindowOpen.call(this, url, ...args);
    };

    this._isInterceptorReady = true;
    console.log('[ShinhanScraper] All interceptors installed (Blob URL + AnchorClick + MutationObserver + window.open)');
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
   * Interceptor sẽ capture data thay vì download về máy.
   */
  async downloadPdf(invoice) {
    if (!invoice._hasPdfLink && !invoice.pdf_url) {
      return { pdf_base64: null, pdf_filename: null, pdf_status: 'no_link' };
    }

    try {
      console.log(`[ShinhanScraper] Download PDF cho HĐ ${invoice.invoice_number} (row ${invoice._rowIndex})`);

      // Ghi nhận số file trước khi click
      const beforeCount = this._interceptedFiles.length;

      // Tìm link PDF trong DOM
      const pdfLink = this._findLinkInRow(invoice._rowIndex, 'PDF');
      if (!pdfLink) {
        console.warn(`[ShinhanScraper] Không tìm thấy link PDF cho row ${invoice._rowIndex}`);
        return { pdf_base64: null, pdf_filename: null, pdf_status: 'error', pdf_error: 'Không tìm thấy link PDF' };
      }

      // Trigger Angular click event (KHÔNG dùng .click() vì đã bị override)
      // Dùng dispatchEvent để Angular nhận được event
      console.log(`[ShinhanScraper] Dispatching click event on PDF link for row ${invoice._rowIndex}...`);
      pdfLink.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
      }));

      // Đợi interceptor capture file (tối đa 15 giây)
      const result = await this._waitForNewFile(beforeCount, 15000);

      if (result) {
        const filename = result.filename || `shinhan_${invoice.invoice_number}.pdf`;
        console.log(`[ShinhanScraper] PDF captured: ${invoice.invoice_number}, size=${result.base64.length}`);
        return { pdf_base64: result.base64, pdf_filename: filename, pdf_status: 'downloaded' };
      }

      console.warn(`[ShinhanScraper] Không capture được PDF cho ${invoice.invoice_number} sau 15s`);
      console.log(`[ShinhanScraper] Intercepted files total: ${this._interceptedFiles.length}, before: ${beforeCount}`);
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

      const beforeCount = this._interceptedFiles.length;

      const xmlLink = this._findLinkInRow(invoice._rowIndex, 'XML');
      if (!xmlLink) {
        return { xml_base64: null, xml_filename: null };
      }

      xmlLink.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
      }));

      const result = await this._waitForNewFile(beforeCount, 15000);

      if (result) {
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

  /**
   * Đợi file mới xuất hiện trong _interceptedFiles.
   * So sánh với beforeCount để biết có file mới hay không.
   */
  _waitForNewFile(beforeCount, timeout = 15000) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const interval = setInterval(() => {
        // Tìm file mới (sau beforeCount)
        if (this._interceptedFiles.length > beforeCount) {
          // Lấy file mới nhất
          const newFile = this._interceptedFiles[this._interceptedFiles.length - 1];
          if (newFile.base64) {
            clearInterval(interval);
            resolve(newFile);
            return;
          }
        }

        if (Date.now() - startTime > timeout) {
          clearInterval(interval);
          resolve(null);
        }
      }, 200);
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
