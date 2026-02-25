/**
 * api-client.js
 * Client gọi API Odoo từ Extension.
 * Xử lý authentication, batch upload, retry logic.
 */

const DEFAULT_TIMEOUT = 30000; // 30 giây
const MAX_RETRIES = 3;
const RETRY_DELAY = 2000; // 2 giây

/**
 * Gọi API với retry logic.
 * @param {string} url - URL endpoint
 * @param {Object} options - Fetch options
 * @param {number} retries - Số lần thử lại còn lại
 * @returns {Response}
 */
async function fetchWithRetry(url, options, retries = MAX_RETRIES) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (retries > 0 && (error.name === 'AbortError' || error.name === 'TypeError')) {
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      return fetchWithRetry(url, options, retries - 1);
    }
    throw error;
  }
}

/**
 * OdooApiClient - Class chính để giao tiếp với Odoo API.
 */
export class OdooApiClient {
  /**
   * @param {string} odooUrl - URL Odoo server (VD: http://localhost:8069)
   * @param {string} apiToken - Token xác thực
   */
  constructor(odooUrl, apiToken) {
    this.odooUrl = odooUrl.replace(/\/$/, '');
    this.apiToken = apiToken;
  }

  /**
   * Tạo headers chuẩn cho request.
   * @returns {Object}
   */
  _getHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-Extension-Token': this.apiToken,
      'Accept': 'application/json',
    };
  }

  /**
   * Kiểm tra kết nối đến Odoo.
   * @returns {Object} { success, message }
   */
  async healthCheck() {
    try {
      const response = await fetchWithRetry(
        `${this.odooUrl}/api/einvoice/health`,
        {
          method: 'GET',
          headers: this._getHeaders(),
        },
        1
      );
      const data = await response.json();
      return { success: response.ok, message: data.message || 'OK', status: response.status };
    } catch (error) {
      return { success: false, message: error.message, status: 0 };
    }
  }

  /**
   * Đồng bộ một hóa đơn lên Odoo staging.
   * @param {Object} invoice - Dữ liệu hóa đơn
   * @param {string} sessionId - Session ID
   * @returns {Object} Kết quả tạo staging
   */
  async syncInvoice(invoice, sessionId) {
    const payload = { ...invoice, session_id: sessionId };

    try {
      const response = await fetchWithRetry(
        `${this.odooUrl}/api/einvoice/staging/create`,
        {
          method: 'POST',
          headers: this._getHeaders(),
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (response.status === 201) {
        return { success: true, staging_id: data.staging_id, invoice_number: invoice.invoice_number };
      } else if (response.status === 409) {
        return { success: false, duplicate: true, existing_id: data.existing_id, invoice_number: invoice.invoice_number };
      } else {
        return { success: false, error: data.error || `HTTP ${response.status}`, invoice_number: invoice.invoice_number };
      }
    } catch (error) {
      return { success: false, error: error.message, invoice_number: invoice.invoice_number };
    }
  }

  /**
   * Đồng bộ nhiều hóa đơn theo batch.
   * @param {Array} invoices - Danh sách hóa đơn
   * @param {string} sessionId - Session ID
   * @param {Function} onProgress - Callback tiến trình (index, total, result)
   * @returns {Object} Kết quả tổng hợp
   */
  async syncBatch(invoices, sessionId, onProgress = null) {
    const results = {
      total: invoices.length,
      created: 0,
      duplicates: 0,
      errors: 0,
      details: [],
    };

    // Chia thành các batch nhỏ
    const batchSize = 10;
    const batches = [];
    for (let i = 0; i < invoices.length; i += batchSize) {
      batches.push(invoices.slice(i, i + batchSize));
    }

    let processedCount = 0;

    for (const batch of batches) {
      try {
        const response = await fetchWithRetry(
          `${this.odooUrl}/api/einvoice/staging/batch`,
          {
            method: 'POST',
            headers: this._getHeaders(),
            body: JSON.stringify({
              session_id: sessionId,
              invoices: batch,
            }),
          }
        );

        const data = await response.json();

        if (response.ok || response.status === 207) {
          results.created += data.created || 0;
          results.duplicates += data.duplicates || 0;
          results.errors += data.errors || 0;
          if (data.results) {
            results.details.push(...data.results);
          }
        } else {
          // Batch thất bại hoàn toàn - thử từng cái
          for (const invoice of batch) {
            const singleResult = await this.syncInvoice(invoice, sessionId);
            results.details.push(singleResult);
            if (singleResult.success) results.created++;
            else if (singleResult.duplicate) results.duplicates++;
            else results.errors++;

            processedCount++;
            if (onProgress) {
              onProgress(processedCount, invoices.length, singleResult);
            }
          }
          continue;
        }
      } catch (error) {
        // Network error - thử từng cái
        for (const invoice of batch) {
          results.errors++;
          results.details.push({
            success: false,
            error: error.message,
            invoice_number: invoice.invoice_number,
          });
        }
      }

      processedCount += batch.length;
      if (onProgress) {
        onProgress(processedCount, invoices.length, null);
      }
    }

    return results;
  }

  /**
   * Lấy danh sách staging từ Odoo.
   * @param {Object} params - Query params (limit, offset, status)
   * @returns {Object} Danh sách staging
   */
  async getStagingList(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = `${this.odooUrl}/api/einvoice/staging/list${queryString ? '?' + queryString : ''}`;

    try {
      const response = await fetchWithRetry(url, {
        method: 'GET',
        headers: this._getHeaders(),
      });
      return await response.json();
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
}

/**
 * Tạo OdooApiClient từ config đã lưu.
 * @param {Object} config - Config từ storage
 * @returns {OdooApiClient}
 */
export function createApiClient(config) {
  return new OdooApiClient(config.odooUrl, config.apiToken);
}
