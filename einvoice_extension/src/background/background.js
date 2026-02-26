/**
 * background.js
 * Service Worker cho Chrome/Edge Extension.
 *
 * Luồng hoạt động mới (DOM-based scraping):
 * 1. Popup gửi FETCH_INVOICES → Background
 * 2. Background tìm tab đang mở các trang hóa đơn
 * 3. Background gửi SCRAPE_INVOICES → Content script trên tab đó
 * 4. Content script scrape DOM → trả về danh sách hóa đơn
 * 5. Background tổng hợp → trả về Popup
 *
 * Background KHÔNG trực tiếp truy cập DOM trang web.
 * Tất cả scraping được thực hiện bởi content scripts.
 */

// ====================================================================
// State
// ====================================================================
const activeTabs = {}; // { source: tabId }

// ====================================================================
// Message Handler
// ====================================================================
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'FETCH_INVOICES':
      handleFetchInvoices(message.payload).then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'SYNC_INVOICES':
      handleSyncInvoices(message.payload).then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'HEALTH_CHECK':
      handleHealthCheck().then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'CHECK_TABS':
      handleCheckTabs().then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'CONTENT_SCRIPT_READY':
      // Lưu tab ID khi content script báo sẵn sàng
      if (sender.tab && message.source) {
        activeTabs[message.source] = sender.tab.id;
        console.log(`[Background] Content script ready: ${message.source} on tab ${sender.tab.id}`);
      }
      return false;

    case 'PDF_DOWNLOAD_PROGRESS':
      // Forward progress đến popup
      chrome.runtime.sendMessage({
        type: 'FETCH_PROGRESS',
        source: message.source,
        processed: message.processed,
        total: message.total,
      }).catch(() => {});
      return false;

    default:
      return false;
  }
});

// ====================================================================
// Check Tabs - Tìm các tab đang mở trang hóa đơn
// ====================================================================
async function handleCheckTabs() {
  const sourcePatterns = {
    grab: ['*://vn.einvoice.grab.com/*', '*://*.einvoice.grab.com/*'],
    tracuu: ['*://spv.tracuuhoadon.online/*', '*://*.tracuuhoadon.online/*'],
    shinhan: ['*://einvoice.shinhan.com.vn/*', '*://*.shinhan.com.vn/*'],
  };

  const results = {};

  for (const [source, patterns] of Object.entries(sourcePatterns)) {
    try {
      const tabs = await chrome.tabs.query({ url: patterns });
      if (tabs.length > 0) {
        // Ping content script để kiểm tra
        try {
          const response = await chrome.tabs.sendMessage(tabs[0].id, { type: 'PING' });
          results[source] = {
            found: true,
            tabId: tabs[0].id,
            url: tabs[0].url,
            loggedIn: response?.loggedIn || false,
            scraperReady: response?.scraperReady || false,
          };
          activeTabs[source] = tabs[0].id;
        } catch (e) {
          results[source] = {
            found: true,
            tabId: tabs[0].id,
            url: tabs[0].url,
            loggedIn: false,
            scraperReady: false,
            error: 'Content script chưa sẵn sàng. Hãy tải lại trang.',
          };
        }
      } else {
        results[source] = { found: false };
      }
    } catch (e) {
      results[source] = { found: false, error: e.message };
    }
  }

  return { success: true, tabs: results };
}

// ====================================================================
// Fetch Invoices - Gửi lệnh scrape đến content scripts
// ====================================================================
async function handleFetchInvoices(payload) {
  const { sources = ['grab', 'tracuu', 'shinhan'] } = payload;

  const results = {
    success: true,
    invoices: [],
    errors: {},
    stats: { grab: 0, tracuu: 0, shinhan: 0 },
  };

  // Tìm tabs đang mở
  await handleCheckTabs();

  // Fetch từng nguồn
  const fetchPromises = sources.map(source => fetchFromTab(source));
  const sourceResults = await Promise.allSettled(fetchPromises);

  sources.forEach((source, index) => {
    const result = sourceResults[index];
    if (result.status === 'fulfilled' && result.value.success) {
      const invoices = result.value.invoices || [];
      results.invoices.push(...invoices);
      results.stats[source] = invoices.length;
    } else {
      const error = result.status === 'fulfilled'
        ? result.value.error
        : (result.reason?.message || 'Lỗi không xác định');
      results.errors[source] = error;
      console.error(`[Background] Lỗi fetch từ ${source}:`, error);
    }
  });

  return results;
}

/**
 * Gửi lệnh scrape đến content script trên tab cụ thể.
 */
async function fetchFromTab(source) {
  const tabId = activeTabs[source];

  if (!tabId) {
    const sourceNames = { grab: 'Grab', tracuu: 'Tracuuhoadon', shinhan: 'Shinhan' };
    const sourceUrls = {
      grab: 'vn.einvoice.grab.com',
      tracuu: 'spv.tracuuhoadon.online',
      shinhan: 'einvoice.shinhan.com.vn',
    };
    return {
      success: false,
      error: `Chưa mở trang ${sourceNames[source]}. Hãy mở ${sourceUrls[source]} và đăng nhập trước.`,
    };
  }

  try {
    // Inject scraper script nếu chưa có
    await injectScraperIfNeeded(tabId, source);

    // Gửi lệnh scrape
    const response = await chrome.tabs.sendMessage(tabId, {
      type: 'SCRAPE_INVOICES',
    });

    if (!response) {
      return {
        success: false,
        error: `Không nhận được phản hồi từ trang ${source}. Hãy tải lại trang.`,
      };
    }

    if (response.needLogin) {
      return {
        success: false,
        error: response.error || `Chưa đăng nhập vào ${source}`,
      };
    }

    // Nếu scrape thành công, tải PDF cho các hóa đơn có link
    if (response.success && response.invoices && response.invoices.length > 0) {
      const invoicesWithPdfLink = response.invoices.filter(inv => inv.pdf_url);

      if (invoicesWithPdfLink.length > 0) {
        try {
          const pdfResponse = await chrome.tabs.sendMessage(tabId, {
            type: 'DOWNLOAD_PDFS_BATCH',
            payload: { invoices: invoicesWithPdfLink },
          });

          if (pdfResponse && pdfResponse.success) {
            // Merge PDF data vào invoices
            const pdfMap = {};
            pdfResponse.results.forEach(r => {
              pdfMap[r.invoice_number] = r;
            });

            response.invoices = response.invoices.map(inv => {
              const pdfData = pdfMap[inv.invoice_number];
              if (pdfData) {
                return { ...inv, ...pdfData };
              }
              return inv;
            });
          }
        } catch (pdfErr) {
          console.warn(`[Background] Lỗi tải PDF batch cho ${source}:`, pdfErr);
        }
      }
    }

    return response;
  } catch (error) {
    return {
      success: false,
      error: `Lỗi giao tiếp với trang ${source}: ${error.message}. Hãy tải lại trang.`,
    };
  }
}

/**
 * Inject scraper script vào tab nếu chưa có.
 */
async function injectScraperIfNeeded(tabId, source) {
  const scraperFiles = {
    grab: 'src/content/grab-scraper.js',
    tracuu: 'src/content/tracuu-scraper.js',
    shinhan: 'src/content/shinhan-scraper.js',
  };

  const file = scraperFiles[source];
  if (!file) return;

  try {
    // Kiểm tra xem scraper đã được inject chưa
    const [checkResult] = await chrome.scripting.executeScript({
      target: { tabId },
      func: (src) => {
        const classNames = {
          grab: 'GrabScraper',
          tracuu: 'TracuuScraper',
          shinhan: 'ShinhanScraper',
        };
        return typeof window[classNames[src]] !== 'undefined';
      },
      args: [source],
    });

    if (checkResult && checkResult.result) {
      return; // Đã inject rồi
    }

    // Inject scraper
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [file],
    });

    console.log(`[Background] Injected ${file} into tab ${tabId}`);

    // Đợi một chút để script load
    await new Promise(resolve => setTimeout(resolve, 300));
  } catch (error) {
    console.warn(`[Background] Lỗi inject scraper cho ${source}:`, error);
  }
}

// ====================================================================
// Sync Invoices - Đồng bộ lên Odoo
// ====================================================================
async function handleSyncInvoices(payload) {
  const { invoices, sessionId } = payload;

  // Lấy config từ storage
  const config = await getConfig();

  if (!config.odooUrl || !config.apiToken) {
    return {
      success: false,
      error: 'Chưa cấu hình Odoo URL và API Token. Vui lòng vào Cài đặt.',
    };
  }

  const currentSessionId = sessionId || `session_${Date.now()}`;
  const results = {
    created: 0,
    duplicates: 0,
    errors: 0,
    details: [],
  };

  const BATCH_SIZE = 5;

  for (let i = 0; i < invoices.length; i += BATCH_SIZE) {
    const batch = invoices.slice(i, i + BATCH_SIZE);

    for (const invoice of batch) {
      try {
        const body = {
          invoice_number: invoice.invoice_number,
          invoice_code: invoice.invoice_code || '',
          invoice_symbol: invoice.invoice_symbol || '',
          invoice_date: invoice.invoice_date || '',
          source: invoice.source,
          seller_tax_code: invoice.seller_tax_code || '',
          seller_name: invoice.seller_name || '',
          amount_untaxed: invoice.amount_untaxed || 0,
          amount_tax: invoice.amount_tax || 0,
          amount_total: invoice.amount_total || 0,
          pdf_base64: invoice.pdf_base64 || null,
          pdf_filename: invoice.pdf_filename || null,
          xml_base64: invoice.xml_base64 || null,
          xml_filename: invoice.xml_filename || null,
          session_id: currentSessionId,
        };

        const response = await fetch(`${config.odooUrl}/api/einvoice/staging/create`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Extension-Token': config.apiToken,
          },
          body: JSON.stringify(body),
        });

        const data = await response.json();

        if (response.status === 201 && data.success) {
          results.created++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'created',
            staging_id: data.staging_id,
          });
        } else if (response.status === 409 || data.duplicate) {
          results.duplicates++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'duplicate',
          });
        } else {
          results.errors++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'error',
            error: data.error || `HTTP ${response.status}`,
          });
        }
      } catch (error) {
        results.errors++;
        results.details.push({
          invoice_number: invoice.invoice_number,
          status: 'error',
          error: error.message,
        });
      }
    }

    // Gửi progress
    chrome.runtime.sendMessage({
      type: 'SYNC_PROGRESS',
      processed: Math.min(i + BATCH_SIZE, invoices.length),
      total: invoices.length,
    }).catch(() => {});
  }

  return { success: true, ...results };
}

// ====================================================================
// Health Check
// ====================================================================
async function handleHealthCheck() {
  const config = await getConfig();
  if (!config.odooUrl || !config.apiToken) {
    return { success: false, error: 'Chưa cấu hình Odoo URL và API Token' };
  }

  try {
    const response = await fetch(`${config.odooUrl}/api/einvoice/health`, {
      method: 'GET',
      headers: { 'X-Extension-Token': config.apiToken },
    });

    const data = await response.json();
    return {
      success: data.success || false,
      message: data.message || 'Kết nối thành công',
      version: data.version,
    };
  } catch (error) {
    return { success: false, error: `Lỗi kết nối: ${error.message}` };
  }
}

// ====================================================================
// Storage Helper
// ====================================================================
async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['odooUrl', 'apiToken', 'fetchDays'], (data) => {
      resolve({
        odooUrl: data.odooUrl || '',
        apiToken: data.apiToken || '',
        fetchDays: data.fetchDays || 30,
      });
    });
  });
}

console.log('[NTP E-Invoice] Background service worker started');
