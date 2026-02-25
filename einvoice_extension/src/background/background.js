/**
 * background.js
 * Service Worker cho Chrome/Edge Extension.
 * Xử lý logic fetch dữ liệu từ 3 nguồn và đồng bộ với Odoo.
 */

import { GrabScraper } from '../content/grab-scraper.js';
import { TracuuScraper } from '../content/tracuu-scraper.js';
import { ShinhanScraper } from '../content/shinhan-scraper.js';
import { saveInvoices, getConfig, saveSession, generateSessionId } from '../utils/storage.js';
import { OdooApiClient } from '../utils/api-client.js';

// Credentials mặc định (sẽ được ghi đè bởi config)
const DEFAULT_CREDENTIALS = {
  grab: { username: 'hoadon_gfb_1000060199', password: 'Ntptech*@1019' },
  tracuu: { username: '0108951191', password: 'Ntptech*1019' },
  shinhan: { username: '0108951191', password: '625843b5' },
};

/**
 * Xử lý message từ popup.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'FETCH_INVOICES':
      handleFetchInvoices(message.payload).then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true; // Async response

    case 'SYNC_INVOICES':
      handleSyncInvoices(message.payload).then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'HEALTH_CHECK':
      handleHealthCheck(message.payload).then(sendResponse).catch(err => {
        sendResponse({ success: false, error: err.message });
      });
      return true;

    case 'CONTENT_SCRIPT_READY':
      console.log('[Background] Content script ready:', message.source, message.url);
      return false;

    default:
      return false;
  }
});

/**
 * Fetch hóa đơn từ tất cả nguồn.
 * @param {Object} payload - { days, sources }
 */
async function handleFetchInvoices(payload) {
  const { days = 30, sources = ['grab', 'tracuu', 'shinhan'] } = payload;
  const config = await getConfig();

  const results = {
    success: true,
    invoices: [],
    errors: {},
    stats: { grab: 0, tracuu: 0, shinhan: 0 },
  };

  // Fetch từng nguồn song song
  const fetchPromises = sources.map(source => fetchFromSource(source, days, config));
  const sourceResults = await Promise.allSettled(fetchPromises);

  sources.forEach((source, index) => {
    const result = sourceResults[index];
    if (result.status === 'fulfilled') {
      const invoices = result.value;
      results.invoices.push(...invoices);
      results.stats[source] = invoices.length;
    } else {
      results.errors[source] = result.reason?.message || 'Lỗi không xác định';
      console.error(`[Background] Lỗi fetch từ ${source}:`, result.reason);
    }
  });

  // Lưu vào local storage
  if (results.invoices.length > 0) {
    await saveInvoices(results.invoices);
  }

  return results;
}

/**
 * Fetch hóa đơn từ một nguồn cụ thể.
 * @param {string} source - 'grab' | 'tracuu' | 'shinhan'
 * @param {number} days
 * @param {Object} config
 */
async function fetchFromSource(source, days, config) {
  const creds = config.credentials?.[source] || DEFAULT_CREDENTIALS[source];

  let scraper;
  switch (source) {
    case 'grab':
      scraper = new GrabScraper();
      break;
    case 'tracuu':
      scraper = new TracuuScraper();
      break;
    case 'shinhan':
      scraper = new ShinhanScraper();
      break;
    default:
      throw new Error(`Nguồn không hợp lệ: ${source}`);
  }

  // Đăng nhập
  const loginSuccess = await scraper.login(creds.username, creds.password);
  if (!loginSuccess) {
    throw new Error(`Đăng nhập thất bại vào ${source}`);
  }

  // Lấy danh sách hóa đơn
  const invoices = await scraper.fetchInvoices(days);

  // Tải PDF cho từng hóa đơn
  const invoicesWithPdf = await downloadPdfsForInvoices(scraper, invoices, source);

  return invoicesWithPdf;
}

/**
 * Tải PDF cho danh sách hóa đơn.
 * @param {Object} scraper - Scraper instance
 * @param {Array} invoices - Danh sách hóa đơn
 * @param {string} source
 */
async function downloadPdfsForInvoices(scraper, invoices, source) {
  const results = [];
  const CONCURRENT_DOWNLOADS = 3; // Tải song song tối đa 3 file

  for (let i = 0; i < invoices.length; i += CONCURRENT_DOWNLOADS) {
    const batch = invoices.slice(i, i + CONCURRENT_DOWNLOADS);
    const downloadPromises = batch.map(async (invoice) => {
      try {
        const pdfResult = await scraper.downloadInvoicePdf(invoice);
        return {
          ...invoice,
          ...pdfResult,
          pdf_status: pdfResult.pdf_base64 ? 'downloaded' : 'error',
        };
      } catch (error) {
        return {
          ...invoice,
          pdf_base64: null,
          pdf_filename: null,
          pdf_status: 'error',
          pdf_error: error.message,
        };
      }
    });

    const batchResults = await Promise.allSettled(downloadPromises);
    batchResults.forEach(result => {
      if (result.status === 'fulfilled') {
        results.push(result.value);
      }
    });

    // Thông báo tiến trình
    chrome.runtime.sendMessage({
      type: 'FETCH_PROGRESS',
      source,
      processed: Math.min(i + CONCURRENT_DOWNLOADS, invoices.length),
      total: invoices.length,
    }).catch(() => {});
  }

  return results;
}

/**
 * Đồng bộ hóa đơn đã chọn lên Odoo.
 * @param {Object} payload - { invoices, sessionId }
 */
async function handleSyncInvoices(payload) {
  const { invoices, sessionId } = payload;
  const config = await getConfig();

  if (!config.odooUrl || !config.apiToken) {
    return {
      success: false,
      error: 'Chưa cấu hình Odoo URL và API Token. Vui lòng vào Cài đặt.',
    };
  }

  const client = new OdooApiClient(config.odooUrl, config.apiToken);
  const currentSessionId = sessionId || generateSessionId();

  const results = await client.syncBatch(invoices, currentSessionId, (processed, total) => {
    // Thông báo tiến trình
    chrome.runtime.sendMessage({
      type: 'SYNC_PROGRESS',
      processed,
      total,
    }).catch(() => {});
  });

  return { success: true, ...results };
}

/**
 * Kiểm tra kết nối đến Odoo.
 */
async function handleHealthCheck(payload) {
  const config = await getConfig();
  if (!config.odooUrl || !config.apiToken) {
    return { success: false, error: 'Chưa cấu hình' };
  }

  const client = new OdooApiClient(config.odooUrl, config.apiToken);
  return client.healthCheck();
}

console.log('[NTP E-Invoice] Background service worker started');
