/**
 * content-bridge.js
 * Content script chạy trên các trang web hóa đơn.
 * Đóng vai trò cầu nối: nhận lệnh từ popup/background → gọi scraper → trả kết quả.
 *
 * Luồng hoạt động:
 * 1. Content script load trên trang web (đã đăng nhập)
 * 2. Popup gửi message SCRAPE_INVOICES → content script scrape DOM
 * 3. Content script trả về danh sách hóa đơn (bao gồm pdf_url, xml_url)
 * 4. Background gửi DOWNLOAD_FILES_BATCH → content script tải PDF/XML
 * 5. Content script trả về base64 data
 *
 * Lưu ý: manifest.json inject scraper file TRƯỚC content-bridge.js
 * nên window.TracuuScraper / window.ShinhanScraper / window.GrabScraper
 * đã sẵn sàng khi content-bridge.js chạy.
 */

(function () {
  'use strict';

  // ====================================================================
  // Xác định nguồn dựa trên URL
  // ====================================================================
  const currentUrl = window.location.href;
  let source = null;

  if (currentUrl.includes('einvoice.grab.com') || currentUrl.includes('grab.com/einvoice')) {
    source = 'grab';
  } else if (currentUrl.includes('tracuuhoadon.online')) {
    source = 'tracuu';
  } else if (currentUrl.includes('einvoice.shinhan.com.vn') || currentUrl.includes('shinhan.com.vn')) {
    source = 'shinhan';
  }

  if (!source) return;

  console.log(`[NTP E-Invoice] Content bridge loaded for: ${source} on ${currentUrl}`);

  // ====================================================================
  // Khởi tạo scraper (đã được inject trước bởi manifest.json)
  // ====================================================================
  let scraper = null;

  function initScraper() {
    switch (source) {
      case 'grab':
        if (typeof window.GrabScraper !== 'undefined') {
          scraper = new window.GrabScraper();
          console.log('[NTP E-Invoice] GrabScraper initialized');
        } else {
          console.warn('[NTP E-Invoice] GrabScraper class not found on window');
        }
        break;
      case 'tracuu':
        if (typeof window.TracuuScraper !== 'undefined') {
          scraper = new window.TracuuScraper();
          console.log('[NTP E-Invoice] TracuuScraper initialized');
        } else {
          console.warn('[NTP E-Invoice] TracuuScraper class not found on window');
        }
        break;
      case 'shinhan':
        if (typeof window.ShinhanScraper !== 'undefined') {
          scraper = new window.ShinhanScraper();
          console.log('[NTP E-Invoice] ShinhanScraper initialized');
        } else {
          console.warn('[NTP E-Invoice] ShinhanScraper class not found on window');
        }
        break;
    }
    return scraper !== null;
  }

  initScraper();

  // ====================================================================
  // Tiện ích: Đợi bảng xuất hiện trong DOM (cho SPA như Angular)
  // ====================================================================
  function waitForTable(timeout = 10000) {
    return new Promise((resolve) => {
      const table = document.querySelector('table');
      if (table && table.querySelectorAll('tbody tr').length > 0) {
        resolve(true);
        return;
      }

      const observer = new MutationObserver(() => {
        const t = document.querySelector('table');
        if (t && t.querySelectorAll('tbody tr').length > 0) {
          observer.disconnect();
          clearTimeout(timer);
          resolve(true);
        }
      });

      observer.observe(document.body, { childList: true, subtree: true });

      const timer = setTimeout(() => {
        observer.disconnect();
        resolve(false);
      }, timeout);
    });
  }

  // ====================================================================
  // Message Handler
  // ====================================================================
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log(`[NTP E-Invoice] Received message: ${message.type}`, message);

    switch (message.type) {
      case 'PING':
        sendResponse({
          success: true,
          source,
          url: currentUrl,
          loggedIn: scraper ? scraper.isLoggedIn() : false,
          scraperReady: scraper !== null,
        });
        return true;

      case 'GET_PAGE_INFO':
        const tables = document.querySelectorAll('table');
        const tableInfo = Array.from(tables).map((t, i) => ({
          index: i,
          headers: Array.from(t.querySelectorAll('th')).map(h => h.textContent.trim()),
          rowCount: t.querySelectorAll('tbody tr').length,
        }));
        sendResponse({
          success: true,
          source,
          url: currentUrl,
          title: document.title,
          loggedIn: scraper ? scraper.isLoggedIn() : false,
          scraperReady: scraper !== null,
          tableCount: tables.length,
          tableInfo,
          bodyText: document.body.innerText.substring(0, 500),
        });
        return true;

      case 'SCRAPE_INVOICES':
        handleScrapeInvoices().then(sendResponse);
        return true;

      case 'DOWNLOAD_PDF':
        handleDownloadPdf(message.payload).then(sendResponse);
        return true;

      case 'DOWNLOAD_PDFS_BATCH':
        handleDownloadPdfsBatch(message.payload).then(sendResponse);
        return true;

      case 'DOWNLOAD_FILES_BATCH':
        handleDownloadFilesBatch(message.payload).then(sendResponse);
        return true;

      case 'FETCH_INVOICE_DETAILS':
        handleFetchInvoiceDetails(message.payload).then(sendResponse);
        return true;

      default:
        return false;
    }
  });

  // ====================================================================
  // Scrape Invoices Handler
  // ====================================================================
  async function handleScrapeInvoices() {
    try {
      if (!scraper) {
        initScraper();
      }

      if (!scraper) {
        return {
          success: false,
          error: `Scraper chưa sẵn sàng cho nguồn: ${source}. Vui lòng tải lại trang.`,
          source,
          debug: {
            grabAvailable: typeof window.GrabScraper !== 'undefined',
            tracuuAvailable: typeof window.TracuuScraper !== 'undefined',
            shinhanAvailable: typeof window.ShinhanScraper !== 'undefined',
          }
        };
      }

      if (!scraper.isLoggedIn()) {
        return {
          success: false,
          error: `Chưa đăng nhập vào ${source}. Vui lòng đăng nhập trước.`,
          source,
          needLogin: true,
        };
      }

      // Với trang SPA (Angular/React), đợi bảng render xong
      if (source === 'shinhan' || source === 'grab') {
        console.log(`[NTP E-Invoice] Đợi bảng render xong cho ${source}...`);
        await waitForTable(8000);
      }

      // Debug: log cấu trúc bảng trước khi scrape
      const tbls = document.querySelectorAll('table');
      console.log(`[NTP E-Invoice] Số bảng trên trang: ${tbls.length}`);
      tbls.forEach((t, i) => {
        const headers = Array.from(t.querySelectorAll('th')).map(h => h.textContent.trim());
        const rows = t.querySelectorAll('tbody tr').length;
        console.log(`[NTP E-Invoice] Bảng ${i}: ${rows} hàng, headers:`, headers);
      });

      // Scrape dữ liệu từ DOM
      const invoices = scraper.scrapeInvoices();

      console.log(`[NTP E-Invoice] Kết quả scrape ${source}: ${invoices.length} hóa đơn`);
      if (invoices.length > 0) {
        console.log('[NTP E-Invoice] Hóa đơn đầu tiên:', JSON.stringify(invoices[0]));
      }

      return {
        success: true,
        source,
        invoices,
        count: invoices.length,
        url: currentUrl,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      console.error(`[NTP E-Invoice] Lỗi scrape ${source}:`, error);
      return {
        success: false,
        error: error.message,
        stack: error.stack,
        source,
      };
    }
  }

  // ====================================================================
  // Download PDF Handler (single)
  // ====================================================================
  async function handleDownloadPdf(payload) {
    try {
      if (!scraper) {
        return { success: false, error: 'Scraper chưa sẵn sàng' };
      }

      const { invoice } = payload;
      const result = await scraper.downloadPdf(invoice);

      return {
        success: result.pdf_status === 'downloaded',
        ...result,
        invoice_number: invoice.invoice_number,
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        pdf_status: 'error',
      };
    }
  }

  // ====================================================================
  // Batch Download PDFs Handler (legacy)
  // ====================================================================
  async function handleDownloadPdfsBatch(payload) {
    try {
      if (!scraper) {
        return { success: false, error: 'Scraper chưa sẵn sàng' };
      }

      const { invoices } = payload;
      const results = [];

      // Xử lý tuần tự (1 lần 1) để tránh conflict khi click simulation
      for (let i = 0; i < invoices.length; i++) {
        const inv = invoices[i];
        try {
          const pdfResult = await scraper.downloadPdf(inv);
          results.push({
            invoice_number: inv.invoice_number,
            ...pdfResult,
          });
          console.log(`[NTP E-Invoice] PDF ${inv.invoice_number}: ${pdfResult.pdf_status}`);
        } catch (e) {
          results.push({
            invoice_number: inv.invoice_number,
            pdf_status: 'error',
            pdf_error: e.message,
          });
        }

        chrome.runtime.sendMessage({
          type: 'PDF_DOWNLOAD_PROGRESS',
          source,
          processed: i + 1,
          total: invoices.length,
        }).catch(() => {});
      }

      return {
        success: true,
        results,
        downloaded: results.filter(r => r.pdf_status === 'downloaded').length,
        total: results.length,
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ====================================================================
  // Batch Download Files (PDF + XML) Handler
  // Xử lý tuần tự để tránh conflict khi dùng click simulation (Shinhan)
  // ====================================================================
  async function handleDownloadFilesBatch(payload) {
    try {
      if (!scraper) {
        return { success: false, error: 'Scraper chưa sẵn sàng' };
      }

      const { invoices } = payload;
      const results = [];

      console.log(`[NTP E-Invoice] Bắt đầu tải files cho ${invoices.length} hóa đơn (source: ${source})`);

      // Xử lý tuần tự (1 lần 1) - quan trọng cho Shinhan click simulation
      for (let i = 0; i < invoices.length; i++) {
        const inv = invoices[i];
        const result = { invoice_number: inv.invoice_number };

        // Tải PDF - kiểm tra có pdf_url hoặc _hasPdfLink (Shinhan click simulation)
        if (inv.pdf_url || inv._hasPdfLink) {
          try {
            const pdfResult = await scraper.downloadPdf(inv);
            Object.assign(result, pdfResult);
            console.log(`[NTP E-Invoice] PDF ${inv.invoice_number}: ${pdfResult.pdf_status}, size=${pdfResult.pdf_base64 ? pdfResult.pdf_base64.length : 0}`);
          } catch (e) {
            result.pdf_status = 'error';
            result.pdf_error = e.message;
            console.warn(`[NTP E-Invoice] PDF error ${inv.invoice_number}:`, e.message);
          }
        } else {
          result.pdf_status = 'no_link';
          console.log(`[NTP E-Invoice] PDF ${inv.invoice_number}: no link`);
        }

        // Tải XML - kiểm tra có xml_url hoặc _hasXmlLink (Shinhan click simulation)
        if ((inv.xml_url || inv._hasXmlLink) && typeof scraper.downloadXml === 'function') {
          try {
            const xmlResult = await scraper.downloadXml(inv);
            Object.assign(result, xmlResult);
            console.log(`[NTP E-Invoice] XML ${inv.invoice_number}: ${xmlResult.xml_base64 ? 'downloaded' : 'empty'}`);
          } catch (e) {
            result.xml_base64 = null;
            result.xml_filename = null;
            console.warn(`[NTP E-Invoice] XML error ${inv.invoice_number}:`, e.message);
          }
        }

        results.push(result);

        // Progress update
        chrome.runtime.sendMessage({
          type: 'PDF_DOWNLOAD_PROGRESS',
          source,
          processed: i + 1,
          total: invoices.length,
        }).catch(() => {});

        // Delay giữa các lần download để tránh rate limit
        if (i < invoices.length - 1) {
          await new Promise(r => setTimeout(r, 500));
        }
      }

      const downloadedPdf = results.filter(r => r.pdf_status === 'downloaded').length;
      const downloadedXml = results.filter(r => r.xml_base64).length;
      console.log(`[NTP E-Invoice] Tải xong: ${downloadedPdf} PDF, ${downloadedXml} XML / ${results.length} tổng`);

      return {
        success: true,
        results,
        downloadedPdf,
        downloadedXml,
        total: results.length,
      };
    } catch (error) {
      console.error(`[NTP E-Invoice] Lỗi tải files batch:`, error);
      return { success: false, error: error.message };
    }
  }

  // ====================================================================
  // Fetch Invoice Details (lấy thêm thông tin NCC từ trang chi tiết)
  // Dùng cho Tracuuhoadon - bảng chính không có tên NCC
  // ====================================================================
  async function handleFetchInvoiceDetails(payload) {
    try {
      if (!scraper || typeof scraper.fetchInvoiceDetail !== 'function') {
        return { success: false, error: 'Scraper không hỗ trợ lấy chi tiết' };
      }

      const { invoices } = payload;
      const results = [];

      console.log(`[NTP E-Invoice] Lấy chi tiết cho ${invoices.length} hóa đơn`);

      for (const inv of invoices) {
        try {
          const detail = await scraper.fetchInvoiceDetail(inv);
          results.push({
            invoice_number: inv.invoice_number,
            ...detail,
          });
          console.log(`[NTP E-Invoice] Chi tiết ${inv.invoice_number}:`, detail);
          // Delay để tránh rate limit
          await new Promise(r => setTimeout(r, 300));
        } catch (e) {
          results.push({
            invoice_number: inv.invoice_number,
            error: e.message,
          });
        }
      }

      return { success: true, results };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ====================================================================
  // Thông báo cho background rằng content script đã load
  // ====================================================================
  chrome.runtime.sendMessage({
    type: 'CONTENT_SCRIPT_READY',
    source,
    url: currentUrl,
    scraperReady: scraper !== null,
  }).catch(() => {});

})();
