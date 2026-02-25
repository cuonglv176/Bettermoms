/**
 * validators.js
 * Validate dữ liệu hóa đơn trước khi đồng bộ.
 */

/**
 * Validate dữ liệu một hóa đơn.
 * @param {Object} invoice - Dữ liệu hóa đơn
 * @returns {Object} { valid: boolean, errors: string[] }
 */
export function validateInvoice(invoice) {
  const errors = [];

  if (!invoice.invoice_number || !invoice.invoice_number.trim()) {
    errors.push('Thiếu số hóa đơn');
  }

  if (!invoice.source || !['grab', 'tracuu', 'shinhan'].includes(invoice.source)) {
    errors.push('Nguồn hóa đơn không hợp lệ');
  }

  if (invoice.invoice_date && !isValidDate(invoice.invoice_date)) {
    errors.push('Ngày lập hóa đơn không hợp lệ');
  }

  if (invoice.amount_total !== undefined && invoice.amount_total < 0) {
    errors.push('Tổng tiền không được âm');
  }

  if (invoice.seller_tax_code && !isValidTaxCode(invoice.seller_tax_code)) {
    errors.push('Mã số thuế không hợp lệ (phải có 10 hoặc 13 chữ số)');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Kiểm tra định dạng ngày (YYYY-MM-DD hoặc DD/MM/YYYY).
 * @param {string} dateStr
 * @returns {boolean}
 */
export function isValidDate(dateStr) {
  if (!dateStr) return false;
  const patterns = [
    /^\d{4}-\d{2}-\d{2}$/,
    /^\d{2}\/\d{2}\/\d{4}$/,
    /^\d{2}-\d{2}-\d{4}$/,
  ];
  return patterns.some(p => p.test(dateStr));
}

/**
 * Kiểm tra mã số thuế Việt Nam (10 hoặc 13 chữ số).
 * @param {string} taxCode
 * @returns {boolean}
 */
export function isValidTaxCode(taxCode) {
  if (!taxCode) return true; // Optional field
  const cleaned = taxCode.replace(/[-\s]/g, '');
  return /^\d{10}(\d{3})?$/.test(cleaned);
}

/**
 * Chuẩn hóa số tiền từ chuỗi sang số.
 * @param {string|number} amount
 * @returns {number}
 */
export function parseAmount(amount) {
  if (typeof amount === 'number') return amount;
  if (!amount) return 0;
  const cleaned = String(amount)
    .replace(/\./g, '')   // Xóa dấu chấm phân cách nghìn
    .replace(/,/g, '.')   // Thay dấu phẩy thành dấu chấm thập phân
    .replace(/[^\d.-]/g, '');
  return parseFloat(cleaned) || 0;
}

/**
 * Chuẩn hóa ngày sang định dạng YYYY-MM-DD.
 * @param {string} dateStr
 * @returns {string|null}
 */
export function normalizeDate(dateStr) {
  if (!dateStr) return null;
  const trimmed = dateStr.trim();

  // DD/MM/YYYY → YYYY-MM-DD
  const ddmmyyyy = trimmed.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (ddmmyyyy) {
    return `${ddmmyyyy[3]}-${ddmmyyyy[2]}-${ddmmyyyy[1]}`;
  }

  // DD-MM-YYYY → YYYY-MM-DD
  const ddmmyyyy2 = trimmed.match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (ddmmyyyy2) {
    return `${ddmmyyyy2[3]}-${ddmmyyyy2[2]}-${ddmmyyyy2[1]}`;
  }

  // YYYY-MM-DD (đã đúng)
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return trimmed;
  }

  return null;
}

/**
 * Validate cấu hình Extension.
 * @param {Object} config
 * @returns {Object} { valid, errors }
 */
export function validateConfig(config) {
  const errors = [];

  if (!config.odooUrl || !config.odooUrl.trim()) {
    errors.push('Chưa nhập URL Odoo server');
  } else if (!config.odooUrl.startsWith('http')) {
    errors.push('URL Odoo phải bắt đầu bằng http:// hoặc https://');
  }

  if (!config.apiToken || !config.apiToken.trim()) {
    errors.push('Chưa nhập API Token');
  }

  if (!config.fetchDays || config.fetchDays < 1 || config.fetchDays > 365) {
    errors.push('Số ngày cần lấy phải từ 1 đến 365');
  }

  return { valid: errors.length === 0, errors };
}
