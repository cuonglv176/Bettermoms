/**
 * pdf-handler.js
 * Xử lý file PDF: tải về, chuyển sang Base64, validate.
 */

const MAX_PDF_SIZE = 10 * 1024 * 1024; // 10MB

/**
 * Tải file PDF từ URL và chuyển sang Base64.
 * @param {string} url - URL của file PDF
 * @param {Object} headers - Headers cho request (cookies, auth, etc.)
 * @returns {Object} { success, base64, filename, size, error }
 */
export async function downloadPdfAsBase64(url, headers = {}) {
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/pdf,application/octet-stream,*/*',
        ...headers,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      return {
        success: false,
        error: `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('pdf') && !contentType.includes('octet-stream')) {
      // Có thể vẫn là PDF dù content-type không đúng
      console.warn('Content-Type không phải PDF:', contentType);
    }

    const blob = await response.blob();

    if (blob.size === 0) {
      return { success: false, error: 'File PDF trống' };
    }

    if (blob.size > MAX_PDF_SIZE) {
      return {
        success: false,
        error: `File PDF quá lớn (${(blob.size / 1024 / 1024).toFixed(1)}MB, tối đa 10MB)`,
      };
    }

    const base64 = await blobToBase64(blob);
    const filename = extractFilenameFromUrl(url) || 'invoice.pdf';

    return {
      success: true,
      base64,
      filename,
      size: blob.size,
      mimeType: blob.type || 'application/pdf',
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Chuyển Blob sang Base64 string.
 * @param {Blob} blob
 * @returns {Promise<string>} Base64 string (không có prefix data:...)
 */
export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      // Xóa prefix "data:application/pdf;base64,"
      const base64 = dataUrl.split(',')[1];
      resolve(base64);
    };
    reader.onerror = () => reject(new Error('Lỗi đọc file'));
    reader.readAsDataURL(blob);
  });
}

/**
 * Trích xuất tên file từ URL.
 * @param {string} url
 * @returns {string}
 */
export function extractFilenameFromUrl(url) {
  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;
    const parts = pathname.split('/');
    const lastPart = parts[parts.length - 1];
    if (lastPart && lastPart.includes('.')) {
      return decodeURIComponent(lastPart);
    }
  } catch (e) {
    // ignore
  }
  return null;
}

/**
 * Validate Base64 string có phải PDF không.
 * @param {string} base64
 * @returns {boolean}
 */
export function isValidPdfBase64(base64) {
  if (!base64) return false;
  try {
    // PDF bắt đầu bằng "%PDF" → Base64 là "JVBE"
    return base64.startsWith('JVBE');
  } catch (e) {
    return false;
  }
}

/**
 * Tạo tên file PDF từ số hóa đơn.
 * @param {string} invoiceNumber
 * @param {string} source
 * @returns {string}
 */
export function generatePdfFilename(invoiceNumber, source) {
  const sanitized = invoiceNumber.replace(/[^a-zA-Z0-9_-]/g, '_');
  const date = new Date().toISOString().split('T')[0];
  return `${source}_${sanitized}_${date}.pdf`;
}
