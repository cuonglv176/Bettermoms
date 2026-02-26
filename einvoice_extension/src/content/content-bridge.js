/**
 * content-bridge.js
 * Content script chạy trên các trang web hóa đơn.
 * Đóng vai trò cầu nối: nhận lệnh từ popup/background → gọi scraper → trả kết quả.
 *
 * Luồng hoạt động mới:
 * 1. Content script load trên trang web (đã đăng nhập)
 * 2. Popup gửi message SCRAPE_INVOICES → content script scrape DOM
 * 3. Content script trả về danh sách hóa đơn
 * 4. Popup gửi message DOWNLOAD_PDF → content script tải PDF
 * 5. Content script trả về PDF base64
 */

(function () {
  'use strict';

  // ====================================================================
  // Xác định nguồn dựa trên URL
  // ====================================================================
  const currentUrl = window.location.href;
  let source = null;

  if (currentUrl.includes('einvoice.grab.com') || currentUrl.includes('grab.com')) {
    source = 'grab';
  } else if (currentUrl.includes('tracuuhoadon.online')) {
    source = 'tracuu';
  } else if (currentUrl.includes('einvoice.shinhan.com.vn') || currentUrl.includes('shinhan.com.vn')) {
    source = 'shinhan';
  }

  if (!source) return;

  console.log(`[NTP E-Invoice] Content bridge loaded for: ${source} on ${currentUrl}`);

  // ====================================================================
  // Load scraper tương ứng
  // ====================================================================
  let scraper = null;

  function initScraper() {
    switch (source) {
      case 'grab':
        if (typeof window.GrabScraper !== 'undefined') {
          scraper = new window.GrabScraper();
        }
        break;
      case 'tracuu':
        if (typeof window.TracuuScraper !== 'undefined') {
          scraper = new window.TracuuScraper();
        }
        break;
      case 'shinhan':
        if (typeof window.ShinhanScraper !== 'undefined') {
          scraper = new window.ShinhanScraper();
        }
        break;
    }
    return scraper !== null;
  }

  // Thử init ngay, nếu chưa có thì đợi
  if (!initScraper()) {
    // Đợi scraper được inject
    const checkInterval = setInterval(() => {
      if (initScraper()) {
        clearInterval(checkInterval);
        console.log(`[NTP E-Invoice] Scraper initialized for: ${source}`);
      }
    }, 200);
    // Timeout sau 10 giây
    setTimeout(() => clearInterval(checkInterval), 10000);
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
        sendResponse({
          success: true,
          source,
          url: currentUrl,
          title: document.title,
          loggedIn: scraper ? scraper.isLoggedIn() : false,
          scraperReady: scraper !== null,
          hasTable: document.querySelector('table') !== null,
          tableCount: document.querySelectorAll('table').length,
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

      // Scrape dữ liệu từ DOM
      const invoices = scraper.scrapeInvoices();

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
      const CONCURRENT = 2; // Tải song song tối đa 2 file

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

        // Gửi progress
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
  }).catch(() => {
    // Background có thể chưa sẵn sàng, bỏ qua
  });
})();
