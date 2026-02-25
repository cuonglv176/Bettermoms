/**
 * popup.js
 * Logic chính cho Extension popup.
 * Quản lý 6 màn hình: Config → Fetching → Preview → Syncing → Result → Settings
 */

import { getConfig, saveConfig, getInvoices, saveInvoices, generateSessionId } from '../utils/storage.js';
import { validateConfig } from '../utils/validators.js';

// ====================================================================
// State Management
// ====================================================================
let state = {
  currentScreen: 'config',
  invoices: [],
  filteredInvoices: [],
  selectedIds: new Set(),
  fetchDays: 30,
  selectedSources: ['grab', 'tracuu', 'shinhan'],
  config: null,
  syncResults: null,
  sessionId: null,
  isFetching: false,
  isSyncing: false,
};

// ====================================================================
// Screen Navigation
// ====================================================================
function showScreen(screenId) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const screen = document.getElementById(`screen-${screenId}`);
  if (screen) {
    screen.classList.add('active');
    state.currentScreen = screenId;
  }
}

// ====================================================================
// Format Helpers
// ====================================================================
function formatCurrency(amount) {
  if (!amount) return '0';
  return new Intl.NumberFormat('vi-VN').format(Math.round(amount));
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;
  } catch { return dateStr; }
}

function getSourceLabel(source) {
  const labels = { grab: 'G', tracuu: 'T', shinhan: 'S' };
  return labels[source] || source.charAt(0).toUpperCase();
}

// ====================================================================
// Toast Notification
// ====================================================================
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, duration);
}

// ====================================================================
// Invoice Table Rendering
// ====================================================================
function renderInvoiceTable(invoices) {
  const tbody = document.getElementById('invoice-table-body');
  if (!invoices || invoices.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align:center;padding:20px;color:#9aa0a6;">
          Không có hóa đơn nào
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = invoices.map((inv, index) => {
    const isSelected = state.selectedIds.has(inv._id);
    const hasPdf = inv.pdf_status === 'downloaded' && inv.pdf_base64;
    const pdfIcon = hasPdf
      ? '<span class="pdf-ok" title="Đã tải PDF">✓</span>'
      : `<span class="pdf-error" title="${inv.pdf_error || 'Lỗi tải PDF'}">✗</span>`;

    return `
      <tr class="${isSelected ? 'selected' : ''}" data-id="${inv._id}">
        <td class="col-check">
          <input type="checkbox" class="row-checkbox" data-id="${inv._id}"
                 ${isSelected ? 'checked' : ''} ${!hasPdf ? 'disabled title="Không có PDF"' : ''}/>
        </td>
        <td class="col-source">
          <span class="source-icon ${inv.source}">${getSourceLabel(inv.source)}</span>
        </td>
        <td class="col-number" title="${inv.invoice_number}">${inv.invoice_number}</td>
        <td class="col-date">${formatDate(inv.invoice_date)}</td>
        <td class="col-seller" title="${inv.seller_name}">${inv.seller_name || '-'}</td>
        <td class="col-amount">${formatCurrency(inv.amount_total)}</td>
        <td class="col-pdf">${pdfIcon}</td>
      </tr>`;
  }).join('');

  // Attach checkbox events
  tbody.querySelectorAll('.row-checkbox').forEach(cb => {
    cb.addEventListener('change', (e) => {
      const id = e.target.dataset.id;
      if (e.target.checked) {
        state.selectedIds.add(id);
        e.target.closest('tr').classList.add('selected');
      } else {
        state.selectedIds.delete(id);
        e.target.closest('tr').classList.remove('selected');
      }
      updatePreviewStats();
    });
  });
}

function updatePreviewStats() {
  const total = state.filteredInvoices.length;
  const selected = state.selectedIds.size;
  const pdfOk = state.filteredInvoices.filter(
    inv => inv.pdf_status === 'downloaded' && inv.pdf_base64
  ).length;

  document.getElementById('preview-total').textContent = `${total} hóa đơn`;
  document.getElementById('preview-selected').textContent = `${selected} đã chọn`;
  document.getElementById('preview-pdf-ok').textContent = `${pdfOk} có PDF`;

  const syncBtn = document.getElementById('btn-sync');
  syncBtn.disabled = selected === 0;
  syncBtn.textContent = selected > 0
    ? `☁️ Đồng bộ ${selected} hóa đơn`
    : '☁️ Đồng bộ lên Hệ thống';
}

function applyFilters() {
  const search = document.getElementById('filter-search').value.toLowerCase();
  const sourceFilter = document.getElementById('filter-source').value;
  const pdfFilter = document.getElementById('filter-pdf').value;

  state.filteredInvoices = state.invoices.filter(inv => {
    const matchSearch = !search ||
      inv.invoice_number.toLowerCase().includes(search) ||
      (inv.seller_name || '').toLowerCase().includes(search) ||
      (inv.seller_tax_code || '').includes(search);

    const matchSource = !sourceFilter || inv.source === sourceFilter;

    const matchPdf = !pdfFilter ||
      (pdfFilter === 'ok' && inv.pdf_status === 'downloaded') ||
      (pdfFilter === 'error' && inv.pdf_status !== 'downloaded');

    return matchSearch && matchSource && matchPdf;
  });

  renderInvoiceTable(state.filteredInvoices);
  updatePreviewStats();
}

// ====================================================================
// Fetch Invoices
// ====================================================================
async function startFetch() {
  if (state.isFetching) return;

  const daysInput = document.getElementById('input-days');
  const days = parseInt(daysInput.value) || 30;

  const sources = [];
  if (document.getElementById('src-grab').checked) sources.push('grab');
  if (document.getElementById('src-tracuu').checked) sources.push('tracuu');
  if (document.getElementById('src-shinhan').checked) sources.push('shinhan');

  if (sources.length === 0) {
    showToast('Vui lòng chọn ít nhất một nguồn dữ liệu');
    return;
  }

  state.isFetching = true;
  state.fetchDays = days;
  state.selectedSources = sources;

  // Reset UI
  sources.forEach(src => {
    document.getElementById(`count-${src}`).textContent = '-';
    document.getElementById(`spinner-${src}`).textContent = '⏳';
  });
  ['grab', 'tracuu', 'shinhan'].forEach(src => {
    if (!sources.includes(src)) {
      const el = document.getElementById(`status-${src}`);
      if (el) el.style.opacity = '0.4';
    }
  });

  document.getElementById('fetch-progress-bar').style.width = '0%';
  document.getElementById('fetch-progress-text').textContent = 'Đang kết nối...';

  showScreen('fetching');

  try {
    // Gửi message đến background để fetch
    const response = await chrome.runtime.sendMessage({
      type: 'FETCH_INVOICES',
      payload: { days, sources },
    });

    if (response.success) {
      state.invoices = response.invoices.map((inv, i) => ({
        ...inv,
        _id: `inv_${i}_${Date.now()}`,
      }));

      // Auto-select tất cả hóa đơn có PDF
      state.selectedIds = new Set(
        state.invoices
          .filter(inv => inv.pdf_status === 'downloaded' && inv.pdf_base64)
          .map(inv => inv._id)
      );

      // Cập nhật stats theo nguồn
      sources.forEach(src => {
        const count = response.stats?.[src] || 0;
        document.getElementById(`count-${src}`).textContent = count;
        document.getElementById(`spinner-${src}`).textContent = count > 0 ? '✅' : '⚠️';
      });

      // Hiển thị lỗi nếu có
      if (Object.keys(response.errors || {}).length > 0) {
        const errorSources = Object.keys(response.errors).join(', ');
        showToast(`Lỗi từ: ${errorSources}. Xem console để biết thêm.`, 5000);
      }

      state.filteredInvoices = [...state.invoices];
      renderInvoiceTable(state.filteredInvoices);
      updatePreviewStats();
      showScreen('preview');
    } else {
      showToast(`Lỗi: ${response.error}`, 5000);
      showScreen('config');
    }
  } catch (error) {
    console.error('[Popup] Lỗi fetch:', error);
    showToast(`Lỗi kết nối: ${error.message}`, 5000);
    showScreen('config');
  } finally {
    state.isFetching = false;
  }
}

// ====================================================================
// Sync Invoices
// ====================================================================
async function startSync() {
  if (state.isSyncing) return;

  const selectedInvoices = state.invoices.filter(inv => state.selectedIds.has(inv._id));
  if (selectedInvoices.length === 0) {
    showToast('Vui lòng chọn ít nhất một hóa đơn');
    return;
  }

  state.isSyncing = true;
  state.sessionId = generateSessionId();

  // Reset sync UI
  document.getElementById('sync-current').textContent = '0';
  document.getElementById('sync-total').textContent = selectedInvoices.length;
  document.getElementById('sync-progress-bar').style.width = '0%';
  document.getElementById('sync-log').innerHTML = '';

  showScreen('syncing');

  // Lắng nghe progress từ background
  const progressListener = (message) => {
    if (message.type === 'SYNC_PROGRESS') {
      const percent = Math.round((message.processed / message.total) * 100);
      document.getElementById('sync-progress-bar').style.width = `${percent}%`;
      document.getElementById('sync-current').textContent = message.processed;
    }
  };
  chrome.runtime.onMessage.addListener(progressListener);

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'SYNC_INVOICES',
      payload: {
        invoices: selectedInvoices,
        sessionId: state.sessionId,
      },
    });

    chrome.runtime.onMessage.removeListener(progressListener);

    state.syncResults = response;

    // Hiển thị kết quả
    document.getElementById('result-success').textContent = response.created || 0;
    document.getElementById('result-duplicate').textContent = response.duplicates || 0;
    document.getElementById('result-error').textContent = response.errors || 0;

    if (response.errors > 0) {
      document.getElementById('result-icon').textContent = '⚠️';
      document.getElementById('result-title').textContent = 'Đồng bộ hoàn tất (có lỗi)';
      const errorSection = document.getElementById('result-errors-section');
      errorSection.style.display = 'block';
      const errorList = document.getElementById('result-errors-list');
      const errorDetails = (response.details || []).filter(d => !d.success && !d.duplicate);
      errorList.innerHTML = errorDetails.map(e =>
        `<div style="font-size:11px;padding:2px 0;">• ${e.invoice_number}: ${e.error}</div>`
      ).join('');
    } else {
      document.getElementById('result-icon').textContent = '✅';
      document.getElementById('result-title').textContent = 'Đồng bộ thành công!';
    }

    showScreen('result');
  } catch (error) {
    chrome.runtime.onMessage.removeListener(progressListener);
    console.error('[Popup] Lỗi sync:', error);
    showToast(`Lỗi đồng bộ: ${error.message}`, 5000);
    showScreen('preview');
  } finally {
    state.isSyncing = false;
  }
}

// ====================================================================
// Settings
// ====================================================================
async function loadSettings() {
  const config = await getConfig();
  state.config = config;
  document.getElementById('setting-odoo-url').value = config.odooUrl || '';
  document.getElementById('setting-api-token').value = config.apiToken || '';
  document.getElementById('setting-batch-size').value = config.batchSize || 10;
}

async function saveSettings() {
  const odooUrl = document.getElementById('setting-odoo-url').value.trim();
  const apiToken = document.getElementById('setting-api-token').value.trim();
  const batchSize = parseInt(document.getElementById('setting-batch-size').value) || 10;

  const config = { odooUrl, apiToken, batchSize, fetchDays: state.fetchDays };
  const validation = validateConfig(config);

  const statusEl = document.getElementById('settings-status');

  if (!validation.valid) {
    statusEl.className = 'settings-status error';
    statusEl.textContent = validation.errors.join('. ');
    return;
  }

  await saveConfig(config);
  state.config = config;

  statusEl.className = 'settings-status success';
  statusEl.textContent = '✓ Đã lưu cài đặt thành công!';
  setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
}

async function testConnection() {
  const statusEl = document.getElementById('settings-status');
  statusEl.className = 'settings-status';
  statusEl.style.display = 'block';
  statusEl.textContent = '🔌 Đang kiểm tra kết nối...';

  const response = await chrome.runtime.sendMessage({
    type: 'HEALTH_CHECK',
    payload: {},
  });

  if (response.success) {
    statusEl.className = 'settings-status success';
    statusEl.textContent = '✅ Kết nối thành công! ' + (response.message || '');
  } else {
    statusEl.className = 'settings-status error';
    statusEl.textContent = '❌ Lỗi kết nối: ' + (response.error || 'Không xác định');
  }
}

async function checkConnection() {
  const statusEl = document.getElementById('connection-status');
  const textEl = document.getElementById('connection-text');

  textEl.textContent = 'Đang kiểm tra...';
  statusEl.className = 'status-bar status-unknown';

  const response = await chrome.runtime.sendMessage({
    type: 'HEALTH_CHECK',
    payload: {},
  });

  if (response.success) {
    statusEl.className = 'status-bar status-ok';
    textEl.textContent = 'Đã kết nối Odoo';
  } else {
    statusEl.className = 'status-bar status-error';
    textEl.textContent = response.error || 'Không thể kết nối';
  }
}

// ====================================================================
// Initialize
// ====================================================================
document.addEventListener('DOMContentLoaded', async () => {
  // Load config
  await loadSettings();

  // Auto check connection
  checkConnection().catch(() => {});

  // ---- Config Screen Events ----
  document.getElementById('btn-start-fetch').addEventListener('click', startFetch);
  document.getElementById('btn-check-connection').addEventListener('click', checkConnection);
  document.getElementById('btn-settings').addEventListener('click', () => {
    loadSettings();
    showScreen('settings');
  });

  // ---- Fetching Screen Events ----
  document.getElementById('btn-cancel-fetch').addEventListener('click', () => {
    state.isFetching = false;
    showScreen('config');
  });

  // Listen for fetch progress from background
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'FETCH_PROGRESS') {
      const percent = Math.round((message.processed / message.total) * 100);
      document.getElementById('fetch-progress-bar').style.width = `${percent}%`;
      document.getElementById('fetch-progress-text').textContent =
        `${message.source}: ${message.processed}/${message.total} hóa đơn`;
      document.getElementById(`count-${message.source}`).textContent = message.processed;
    }
  });

  // ---- Preview Screen Events ----
  document.getElementById('btn-select-all').addEventListener('click', () => {
    state.filteredInvoices
      .filter(inv => inv.pdf_status === 'downloaded' && inv.pdf_base64)
      .forEach(inv => state.selectedIds.add(inv._id));
    renderInvoiceTable(state.filteredInvoices);
    updatePreviewStats();
  });

  document.getElementById('btn-deselect-all').addEventListener('click', () => {
    state.selectedIds.clear();
    renderInvoiceTable(state.filteredInvoices);
    updatePreviewStats();
  });

  document.getElementById('check-all-header').addEventListener('change', (e) => {
    if (e.target.checked) {
      state.filteredInvoices
        .filter(inv => inv.pdf_status === 'downloaded' && inv.pdf_base64)
        .forEach(inv => state.selectedIds.add(inv._id));
    } else {
      state.filteredInvoices.forEach(inv => state.selectedIds.delete(inv._id));
    }
    renderInvoiceTable(state.filteredInvoices);
    updatePreviewStats();
  });

  document.getElementById('btn-sync').addEventListener('click', startSync);
  document.getElementById('btn-rescan').addEventListener('click', () => {
    state.invoices = [];
    state.selectedIds.clear();
    showScreen('config');
  });

  // Filter events
  document.getElementById('filter-search').addEventListener('input', applyFilters);
  document.getElementById('filter-source').addEventListener('change', applyFilters);
  document.getElementById('filter-pdf').addEventListener('change', applyFilters);

  // ---- Result Screen Events ----
  document.getElementById('btn-done').addEventListener('click', () => {
    state.invoices = [];
    state.selectedIds.clear();
    showScreen('config');
  });

  document.getElementById('btn-view-odoo').addEventListener('click', async () => {
    const config = await getConfig();
    if (config.odooUrl) {
      chrome.tabs.create({ url: `${config.odooUrl}/web#action=ntp_einvoice_bizzi.action_invoice_staging_list` });
    }
  });

  // ---- Settings Screen Events ----
  document.getElementById('btn-back-settings').addEventListener('click', () => {
    showScreen('config');
  });

  document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
  document.getElementById('btn-test-connection').addEventListener('click', testConnection);

  document.getElementById('btn-toggle-token').addEventListener('click', () => {
    const input = document.getElementById('setting-api-token');
    input.type = input.type === 'password' ? 'text' : 'password';
  });

  // Initial screen
  showScreen('config');
});
