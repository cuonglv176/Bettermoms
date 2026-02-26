/**
 * content-bridge.js
 * Content script chạy trên các trang web hóa đơn.
 * Đóng vai trò cầu nối: nhận lệnh từ popup/background → gọi scraper → trả kết quả.
 *
 * Luồng hoạt động:
 * 1. Content script load trên trang web (đã đăng nhập)
 * 2. Popup gửi message SCRAPE_INVOICES → content script scrape DOM
 * 3. Content script trả về danh sách hóa đơn
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
      // Kiểm tra ngay
      const table = document.querySelector('table');
      if (table && table.querySelectorAll('tbody tr').length > 0) {
        resolve(true);
        return;
      }

      // Dùng MutationObserver để đợi DOM thay đổi
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
        resolve(false); // Timeout nhưng vẫn thử scrape
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
        return true; // Async response

      case 'DOWNLOAD_PDF':
        handleDownloadPdf(message.payload).then(sendResponse);
        return true;

      case 'DOWNLOAD_PDFS_BATCH':
        handleDownloadPdfsBatch(message.payload).then(sendResponse);
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
      // Đảm bảo scraper đã sẵn sàng
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

      // Kiểm tra đăng nhập
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
      const tables = document.querySelectorAll('table');
      console.log(`[NTP E-Invoice] Số bảng trên trang: ${tables.length}`);
      tables.forEach((t, i) => {
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
  // Download PDF Handler
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
  // Batch Download PDFs Handler
  // ====================================================================
  async function handleDownloadPdfsBatch(payload) {
    try {
      if (!scraper) {
        return { success: false, error: 'Scraper chưa sẵn sàng' };
      }

      const { invoices } = payload;
      const results = [];
      const CONCURRENT = 2;

      for (let i = 0; i < invoices.length; i += CONCURRENT) {
        const batch = invoices.slice(i, i + CONCURRENT);
        const batchResults = await Promise.allSettled(
          batch.map(inv => scraper.downloadPdf(inv))
        );

        batchResults.forEach((result, j) => {
          const inv = batch[j];
          if (result.status === 'fulfilled') {
            results.push({
              invoice_number: inv.invoice_number,
              ...result.value,
            });
          } else {
            results.push({
              invoice_number: inv.invoice_number,
              pdf_status: 'error',
              pdf_error: result.reason?.message || 'Lỗi không xác định',
            });
          }
        });

        chrome.runtime.sendMessage({
          type: 'PDF_DOWNLOAD_PROGRESS',
          source,
          processed: Math.min(i + CONCURRENT, invoices.length),
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
  // Thông báo cho background rằng content script đã load
  // ====================================================================
  chrome.runtime.sendMessage({
    type: 'CONTENT_SCRIPT_READY',
    source,
    url: currentUrl,
    scraperReady: scraper !== null,
  }).catch(() => {});

})();
