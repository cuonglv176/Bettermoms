/**
 * storage.js
 * Quản lý lưu trữ dữ liệu local cho Extension.
 * Sử dụng chrome.storage.local để lưu cấu hình và hóa đơn tạm thời.
 */

const STORAGE_KEYS = {
  CONFIG: 'ntp_einvoice_config',
  INVOICES: 'ntp_einvoice_invoices',
  SESSION: 'ntp_einvoice_session',
  LAST_SYNC: 'ntp_einvoice_last_sync',
};

/**
 * Lưu cấu hình Extension.
 * @param {Object} config - Cấu hình cần lưu
 */
export async function saveConfig(config) {
  return chrome.storage.local.set({ [STORAGE_KEYS.CONFIG]: config });
}

/**
 * Lấy cấu hình Extension.
 * @returns {Object} Cấu hình hiện tại
 */
export async function getConfig() {
  const result = await chrome.storage.local.get(STORAGE_KEYS.CONFIG);
  return result[STORAGE_KEYS.CONFIG] || {
    odooUrl: '',
    apiToken: '',
    fetchDays: 30,
    batchSize: 10,
    autoSync: false,
  };
}

/**
 * Lưu danh sách hóa đơn tạm thời vào local storage.
 * @param {Array} invoices - Danh sách hóa đơn
 */
export async function saveInvoices(invoices) {
  return chrome.storage.local.set({
    [STORAGE_KEYS.INVOICES]: invoices,
    [STORAGE_KEYS.LAST_SYNC]: new Date().toISOString(),
  });
}

/**
 * Lấy danh sách hóa đơn từ local storage.
 * @returns {Array} Danh sách hóa đơn
 */
export async function getInvoices() {
  const result = await chrome.storage.local.get([
    STORAGE_KEYS.INVOICES,
    STORAGE_KEYS.LAST_SYNC,
  ]);
  return {
    invoices: result[STORAGE_KEYS.INVOICES] || [],
    lastSync: result[STORAGE_KEYS.LAST_SYNC] || null,
  };
}

/**
 * Xóa danh sách hóa đơn khỏi local storage.
 */
export async function clearInvoices() {
  return chrome.storage.local.remove([STORAGE_KEYS.INVOICES, STORAGE_KEYS.LAST_SYNC]);
}

/**
 * Lưu session ID hiện tại.
 * @param {string} sessionId
 */
export async function saveSession(sessionId) {
  return chrome.storage.local.set({ [STORAGE_KEYS.SESSION]: sessionId });
}

/**
 * Lấy session ID hiện tại.
 * @returns {string|null}
 */
export async function getSession() {
  const result = await chrome.storage.local.get(STORAGE_KEYS.SESSION);
  return result[STORAGE_KEYS.SESSION] || null;
}

/**
 * Tạo session ID mới.
 * @returns {string} Session ID dạng UUID
 */
export function generateSessionId() {
  return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Xóa toàn bộ dữ liệu Extension.
 */
export async function clearAll() {
  return chrome.storage.local.clear();
}
