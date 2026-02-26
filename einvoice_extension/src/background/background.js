/**
 * background.js
 * Service Worker cho Chrome/Edge Extension.
 *
 * Luồng hoạt động (DOM-based scraping):
 * 1. Popup gửi FETCH_INVOICES → Background
 * 2. Background tìm tab đang mở các trang hóa đơn
 * 3. Background gửi SCRAPE_INVOICES → Content script trên tab đó
 * 4. Content script scrape DOM → trả về danh sách hóa đơn
 * 5. Background tổng hợp → trả về Popup
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
        console.error('[Background] FETCH_INVOICES error:', err);
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'SYNC_INVOICES':
      handleSyncInvoices(message.payload).then(sendResponse).catch(err => {
        console.error('[Background] SYNC_INVOICES error:', err);
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
      if (sender.tab && message.source) {
        activeTabs[message.source] = sender.tab.id;
        console.log(`[Background] Content script ready: ${message.source} on tab ${sender.tab.id}`);
      }
      return false;

    case 'PDF_DOWNLOAD_PROGRESS':
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
      console.log(`[Background] Fetched ${invoices.length} invoices from ${source}`);
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
      return;
    }

    await chrome.scripting.executeScript({
      target: { tabId },
      files: [file],
    });

    console.log(`[Background] Injected ${file} into tab ${tabId}`);
    await new Promise(resolve => setTimeout(resolve, 300));
  } catch (error) {
    console.warn(`[Background] Lỗi inject scraper cho ${source}:`, error);
  }
}

// ====================================================================
// Sync Invoices - Đồng bộ lên Odoo (với error logging chi tiết)
// ====================================================================
async function handleSyncInvoices(payload) {
  const { invoices, sessionId } = payload;

  // Lấy config từ storage
  const config = await getConfig();

  if (!config.odooUrl || !config.apiToken) {
    return {
      success: false,
      error: 'Chưa cấu hình Odoo URL và API Token. Vui lòng vào Cài đặt Extension (⚙️).',
    };
  }

  const currentSessionId = sessionId || `session_${Date.now()}`;
  const results = {
    created: 0,
    duplicates: 0,
    errors: 0,
    details: [],
  };

  console.log(`[Background] ===== BẮT ĐẦU SYNC ${invoices.length} HÓA ĐƠN =====`);
  console.log(`[Background] Odoo URL: ${config.odooUrl}`);
  console.log(`[Background] API Token: ${config.apiToken ? config.apiToken.substring(0, 8) + '...' : 'EMPTY'}`);
  console.log(`[Background] Session ID: ${currentSessionId}`);

  const BATCH_SIZE = 5;

  for (let i = 0; i < invoices.length; i += BATCH_SIZE) {
    const batch = invoices.slice(i, i + BATCH_SIZE);

    for (const invoice of batch) {
      try {
        console.log(`[Background] Syncing invoice: ${invoice.invoice_number} (source: ${invoice.source})`);

        const body = {
          invoice_number: invoice.invoice_number || '',
          invoice_code: invoice.invoice_code || '',
          invoice_symbol: invoice.invoice_symbol || '',
          invoice_date: invoice.invoice_date || '',
          source: invoice.source || 'manual',
          seller_tax_code: invoice.seller_tax_code || '',
          seller_name: invoice.seller_name || '',
          amount_untaxed: parseFloat(invoice.amount_untaxed) || 0,
          amount_tax: parseFloat(invoice.amount_tax) || 0,
          amount_total: parseFloat(invoice.amount_total) || 0,
          pdf_base64: invoice.pdf_base64 || null,
          pdf_filename: invoice.pdf_filename || null,
          xml_base64: invoice.xml_base64 || null,
          xml_filename: invoice.xml_filename || null,
          session_id: currentSessionId,
        };

        console.log(`[Background] Request body (without pdf/xml):`, JSON.stringify({
          ...body,
          pdf_base64: body.pdf_base64 ? `[${body.pdf_base64.length} chars]` : null,
          xml_base64: body.xml_base64 ? `[${body.xml_base64.length} chars]` : null,
        }));

        const apiUrl = `${config.odooUrl}/api/einvoice/staging/create`;
        console.log(`[Background] POST ${apiUrl}`);

        // Odoo type='json' nhận JSON-RPC format:
        // Request: { "jsonrpc": "2.0", "method": "call", "params": { ...data } }
        // Response: { "jsonrpc": "2.0", "id": null, "result": { ...result } }
        //        or { "jsonrpc": "2.0", "id": null, "error": { "code": ..., "message": ..., "data": ... } }
        const jsonRpcBody = {
          jsonrpc: '2.0',
          method: 'call',
          id: Date.now(),
          params: body,
        };

        const response = await fetch(apiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Extension-Token': config.apiToken,
          },
          body: JSON.stringify(jsonRpcBody),
        });

        const responseText = await response.text();
        console.log(`[Background] Response status: ${response.status}`);
        console.log(`[Background] Response body: ${responseText.substring(0, 500)}`);

        let rpcResponse;
        try {
          rpcResponse = JSON.parse(responseText);
        } catch (parseErr) {
          console.error(`[Background] Response is not JSON:`, responseText.substring(0, 200));
          results.errors++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'error',
            error: `HTTP ${response.status}: Response không phải JSON - ${responseText.substring(0, 100)}`,
          });
          continue;
        }

        // Kiểm tra lỗi JSON-RPC level
        if (rpcResponse.error) {
          const rpcError = rpcResponse.error;
          const errorMsg = rpcError.data?.message || rpcError.message || JSON.stringify(rpcError);
          results.errors++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'error',
            error: `Odoo RPC Error: ${errorMsg}`,
          });
          console.error(`[Background] ❌ RPC Error: ${invoice.invoice_number} → ${errorMsg}`);
          continue;
        }

        // Lấy result từ JSON-RPC response
        const data = rpcResponse.result || rpcResponse;

        if (data.success) {
          results.created++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'created',
            staging_id: data.staging_id,
          });
          console.log(`[Background] ✅ Created: ${invoice.invoice_number} → staging_id=${data.staging_id}`);
        } else if (data.duplicate) {
          results.duplicates++;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'duplicate',
            message: data.error || 'Trùng lặp',
          });
          console.log(`[Background] ⚠️ Duplicate: ${invoice.invoice_number}`);
        } else {
          results.errors++;
          const errorMsg = data.error || `HTTP ${response.status}: ${responseText.substring(0, 200)}`;
          results.details.push({
            invoice_number: invoice.invoice_number,
            status: 'error',
            error: errorMsg,
          });
          console.error(`[Background] ❌ Error: ${invoice.invoice_number} → ${errorMsg}`);
        }
      } catch (error) {
        results.errors++;
        const errorMsg = `Network/Fetch error: ${error.message}`;
        results.details.push({
          invoice_number: invoice.invoice_number,
          status: 'error',
          error: errorMsg,
        });
        console.error(`[Background] ❌ Exception syncing ${invoice.invoice_number}:`, error);
      }
    }

    // Gửi progress
    chrome.runtime.sendMessage({
      type: 'SYNC_PROGRESS',
      processed: Math.min(i + BATCH_SIZE, invoices.length),
      total: invoices.length,
    }).catch(() => {});
  }

  console.log(`[Background] ===== KẾT QUẢ SYNC =====`);
  console.log(`[Background] Created: ${results.created}, Duplicates: ${results.duplicates}, Errors: ${results.errors}`);
  console.log(`[Background] Details:`, JSON.stringify(results.details, null, 2));

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
    console.log(`[Background] Health check: ${config.odooUrl}/api/einvoice/health`);
    const response = await fetch(`${config.odooUrl}/api/einvoice/health`, {
      method: 'GET',
      headers: { 'X-Extension-Token': config.apiToken },
    });

    const data = await response.json();
    console.log(`[Background] Health check response:`, data);
    return {
      success: data.success || false,
      message: data.message || 'Kết nối thành công',
      version: data.version,
    };
  } catch (error) {
    console.error(`[Background] Health check failed:`, error);
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
