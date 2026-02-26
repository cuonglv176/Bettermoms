/**
 * popup.js
 * Logic chính cho Extension popup.
 * Quản lý các màn hình: Config → Fetching → Preview → Syncing → Result → Settings
 *
 * Luồng mới:
 * 1. User mở popup → kiểm tra tabs đang mở
 * 2. User bấm "Quét lại" → gửi FETCH_INVOICES → background → content scripts scrape DOM
 * 3. Hiển thị kết quả → User chọn hóa đơn → bấm "Đồng bộ lên Hệ thống"
 */

// ====================================================================
// State Management
// ====================================================================
let state = {
  currentScreen: 'config',
  invoices: [],
  filteredInvoices: [],
  selectedIds: new Set(),
  config: null,
  syncResults: null,
  isFetching: false,
  isSyncing: false,
  tabStatus: {},
};

// ====================================================================
// Initialization
// ====================================================================
document.addEventListener('DOMContentLoaded', async () => {
  // Load config
  state.config = await loadConfig();
  applyConfig();

  // Kiểm tra tabs đang mở
  await checkOpenTabs();

  // Load cached invoices nếu có
  const cached = await loadCachedInvoices();
  if (cached && cached.length > 0) {
    state.invoices = cached;
    state.filteredInvoices = [...cached];
    state.selectedIds = new Set(
      cached.filter(inv => inv.pdf_status === 'downloaded' && inv.pdf_base64).map(inv => inv._id)
    );
    renderInvoiceTable(state.filteredInvoices);
    updatePreviewStats();
    showScreen('preview');
  } else {
    showScreen('config');
  }

  // Bind events
  bindEvents();

  // Listen for progress messages
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'FETCH_PROGRESS') {
      updateFetchProgress(message);
    } else if (message.type === 'SYNC_PROGRESS') {
      updateSyncProgress(message);
    }
  });
});

// ====================================================================
// Config
// ====================================================================
async function loadConfig() {
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

async function saveConfig(config) {
  return new Promise((resolve) => {
    chrome.storage.local.set(config, resolve);
  });
}

function applyConfig() {
  const urlInput = document.getElementById('input-odoo-url');
  const tokenInput = document.getElementById('input-api-token');
  const daysInput = document.getElementById('input-days');

  if (urlInput && state.config.odooUrl) urlInput.value = state.config.odooUrl;
  if (tokenInput && state.config.apiToken) tokenInput.value = state.config.apiToken;
  if (daysInput && state.config.fetchDays) daysInput.value = state.config.fetchDays;
}

// ====================================================================
// Cache Invoices
// ====================================================================
async function loadCachedInvoices() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['cachedInvoices'], (data) => {
      resolve(data.cachedInvoices || []);
    });
  });
}

async function saveCachedInvoices(invoices) {
  // Lưu nhưng bỏ pdf_base64 để tiết kiệm storage
  const light = invoices.map(inv => ({
    ...inv,
    pdf_base64: inv.pdf_base64 ? '[HAS_DATA]' : null,
  }));
  return new Promise((resolve) => {
    chrome.storage.local.set({ cachedInvoices: light }, resolve);
  });
}

// ====================================================================
// Check Open Tabs
// ====================================================================
async function checkOpenTabs() {
  try {
    const response = await chrome.runtime.sendMessage({ type: 'CHECK_TABS' });
    if (response && response.success) {
      state.tabStatus = response.tabs;
      updateTabStatusUI();
    }
  } catch (err) {
    console.warn('[Popup] Lỗi kiểm tra tabs:', err);
  }
}

function updateTabStatusUI() {
  const sources = ['grab', 'tracuu', 'shinhan'];
  sources.forEach(source => {
    const statusEl = document.getElementById(`tab-status-${source}`);
    if (!statusEl) return;

    const info = state.tabStatus[source];
    if (info && info.found) {
      if (info.loggedIn) {
        statusEl.textContent = '✅ Đã đăng nhập';
        statusEl.className = 'tab-status ok';
      } else {
        statusEl.textContent = '⚠️ Chưa đăng nhập';
        statusEl.className = 'tab-status warning';
      }
    } else {
      statusEl.textContent = '❌ Chưa mở trang';
      statusEl.className = 'tab-status error';
    }
  });
}

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
    const parts = dateStr.split('-');
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return dateStr;
  } catch { return dateStr; }
}

function getSourceLabel(source) {
  const labels = { grab: 'G', tracuu: 'T', shinhan: 'S' };
  return labels[source] || source.charAt(0).toUpperCase();
}

function getSourceName(source) {
  const names = { grab: 'Grab', tracuu: 'Tracuuhoadon', shinhan: 'Shinhan' };
  return names[source] || source;
}

// ====================================================================
// Toast Notification
// ====================================================================
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, duration);
}

// ====================================================================
// Invoice Table Rendering
// ====================================================================
function renderInvoiceTable(invoices) {
  const tbody = document.getElementById('invoice-table-body');
  if (!tbody) return;

  if (!invoices || invoices.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align:center;padding:20px;color:#9aa0a6;">
          Không có hóa đơn nào
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = invoices.map((inv) => {
    const isSelected = state.selectedIds.has(inv._id);
    const hasPdf = inv.pdf_status === 'downloaded' && inv.pdf_base64;
    const pdfIcon = hasPdf
      ? '<span class="pdf-ok" title="Đã tải PDF">&#10003;</span>'
      : (inv.pdf_status === 'no_link'
        ? '<span class="pdf-na" title="Không có link PDF">-</span>'
        : '<span class="pdf-error" title="' + (inv.pdf_error || 'Lỗi tải PDF') + '">&#10007;</span>');

    return `
      <tr class="${isSelected ? 'selected' : ''}" data-id="${inv._id}">
        <td class="col-check">
          <input type="checkbox" class="row-checkbox" data-id="${inv._id}"
                 ${isSelected ? 'checked' : ''} />
        </td>
        <td class="col-source">
          <span class="source-icon ${inv.source}">${getSourceLabel(inv.source)}</span>
        </td>
        <td class="col-number" title="${inv.invoice_number}">${inv.invoice_number}</td>
        <td class="col-date">${formatDate(inv.invoice_date)}</td>
        <td class="col-seller" title="${inv.seller_name || ''}">${inv.seller_name || '-'}</td>
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

  const totalEl = document.getElementById('preview-total');
  const selectedEl = document.getElementById('preview-selected');
  const pdfEl = document.getElementById('preview-pdf-ok');

  if (totalEl) totalEl.textContent = `${total} hóa đơn`;
  if (selectedEl) selectedEl.textContent = `${selected} đã chọn`;
  if (pdfEl) pdfEl.textContent = `${pdfOk} có PDF`;

  const syncBtn = document.getElementById('btn-sync');
  if (syncBtn) {
    syncBtn.disabled = selected === 0;
    syncBtn.textContent = selected > 0
      ? `Đồng bộ ${selected} hóa đơn`
      : 'Đồng bộ lên Hệ thống';
  }
}

function applyFilters() {
  const searchEl = document.getElementById('filter-search');
  const sourceEl = document.getElementById('filter-source');
  const pdfEl = document.getElementById('filter-pdf');

  const search = searchEl ? searchEl.value.toLowerCase() : '';
  const sourceFilter = sourceEl ? sourceEl.value : '';
  const pdfFilter = pdfEl ? pdfEl.value : '';

  state.filteredInvoices = state.invoices.filter(inv => {
    const matchSearch = !search ||
      (inv.invoice_number || '').toLowerCase().includes(search) ||
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

  const sources = [];
  const srcGrab = document.getElementById('src-grab');
  const srcTracuu = document.getElementById('src-tracuu');
  const srcShinhan = document.getElementById('src-shinhan');

  if (srcGrab && srcGrab.checked) sources.push('grab');
  if (srcTracuu && srcTracuu.checked) sources.push('tracuu');
  if (srcShinhan && srcShinhan.checked) sources.push('shinhan');

  if (sources.length === 0) {
    showToast('Vui lòng chọn ít nhất một nguồn dữ liệu');
    return;
  }

  state.isFetching = true;

  // Reset UI
  sources.forEach(src => {
    const countEl = document.getElementById(`count-${src}`);
    const spinnerEl = document.getElementById(`spinner-${src}`);
    if (countEl) countEl.textContent = '-';
    if (spinnerEl) spinnerEl.textContent = '⏳';
  });

  const progressBar = document.getElementById('fetch-progress-bar');
  const progressText = document.getElementById('fetch-progress-text');
  if (progressBar) progressBar.style.width = '0%';
  if (progressText) progressText.textContent = 'Đang quét dữ liệu từ các trang web...';

  showScreen('fetching');

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'FETCH_INVOICES',
      payload: { sources },
    });

    if (response && response.invoices && response.invoices.length > 0) {
      // Gán _id nếu chưa có
      state.invoices = response.invoices.map((inv, i) => ({
        ...inv,
        _id: inv._id || `inv_${i}_${Date.now()}`,
      }));

      // Auto-select tất cả hóa đơn
      state.selectedIds = new Set(state.invoices.map(inv => inv._id));

      // Cập nhật stats
      sources.forEach(src => {
        const count = response.stats?.[src] || 0;
        const countEl = document.getElementById(`count-${src}`);
        const spinnerEl = document.getElementById(`spinner-${src}`);
        if (countEl) countEl.textContent = count;
        if (spinnerEl) spinnerEl.textContent = count > 0 ? '✅' : '⚠️';
      });

      // Hiển thị lỗi nếu có
      if (response.errors && Object.keys(response.errors).length > 0) {
        const errorMsgs = Object.entries(response.errors)
          .map(([src, err]) => `${getSourceName(src)}: ${err}`)
          .join('\n');
        showToast(errorMsgs, 5000);
      }

      // Cache và hiển thị
      await saveCachedInvoices(state.invoices);
      state.filteredInvoices = [...state.invoices];
      renderInvoiceTable(state.filteredInvoices);
      updatePreviewStats();
      showScreen('preview');
    } else {
      // Không có hóa đơn nào
      const errorMsg = response?.errors
        ? Object.entries(response.errors).map(([src, err]) => `${getSourceName(src)}: ${err}`).join('\n')
        : 'Không tìm thấy hóa đơn nào. Hãy đảm bảo đã mở và đăng nhập vào các trang web.';
      showToast(errorMsg, 5000);
      showScreen('config');
    }
  } catch (error) {
    console.error('[Popup] Lỗi fetch:', error);
    showToast(`Lỗi: ${error.message}`, 5000);
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

  // Reset sync UI
  const syncCurrent = document.getElementById('sync-current');
  const syncTotal = document.getElementById('sync-total');
  const syncProgressBar = document.getElementById('sync-progress-bar');
  const syncLog = document.getElementById('sync-log');

  if (syncCurrent) syncCurrent.textContent = '0';
  if (syncTotal) syncTotal.textContent = selectedInvoices.length;
  if (syncProgressBar) syncProgressBar.style.width = '0%';
  if (syncLog) syncLog.innerHTML = '';

  showScreen('syncing');

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'SYNC_INVOICES',
      payload: {
        invoices: selectedInvoices,
        sessionId: `session_${Date.now()}`,
      },
    });

    if (response && response.success) {
      state.syncResults = response;

      // Hiển thị kết quả
      const resultCreated = document.getElementById('result-created');
      const resultDuplicates = document.getElementById('result-duplicates');
      const resultErrors = document.getElementById('result-errors');

      if (resultCreated) resultCreated.textContent = response.created || 0;
      if (resultDuplicates) resultDuplicates.textContent = response.duplicates || 0;
      if (resultErrors) resultErrors.textContent = response.errors || 0;

      showScreen('result');
    } else {
      showToast(`Lỗi đồng bộ: ${response?.error || 'Không xác định'}`, 5000);
      showScreen('preview');
    }
  } catch (error) {
    showToast(`Lỗi: ${error.message}`, 5000);
    showScreen('preview');
  } finally {
    state.isSyncing = false;
  }
}

// ====================================================================
// Progress Updates
// ====================================================================
function updateFetchProgress(message) {
  const progressBar = document.getElementById('fetch-progress-bar');
  const progressText = document.getElementById('fetch-progress-text');
  if (message.total > 0) {
    const percent = Math.round((message.processed / message.total) * 100);
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.textContent = `Đang tải PDF: ${message.processed}/${message.total}`;
  }
}

function updateSyncProgress(message) {
  const syncProgressBar = document.getElementById('sync-progress-bar');
  const syncCurrent = document.getElementById('sync-current');
  if (message.total > 0) {
    const percent = Math.round((message.processed / message.total) * 100);
    if (syncProgressBar) syncProgressBar.style.width = `${percent}%`;
    if (syncCurrent) syncCurrent.textContent = message.processed;
  }
}

// ====================================================================
// Select All / Deselect All
// ====================================================================
function selectAll() {
  state.selectedIds = new Set(state.filteredInvoices.map(inv => inv._id));
  renderInvoiceTable(state.filteredInvoices);
  updatePreviewStats();
}

function deselectAll() {
  state.selectedIds.clear();
  renderInvoiceTable(state.filteredInvoices);
  updatePreviewStats();
}

// ====================================================================
// Settings
// ====================================================================
async function saveSettings() {
  const urlInput = document.getElementById('input-odoo-url');
  const tokenInput = document.getElementById('input-api-token');
  const daysInput = document.getElementById('input-days');

  const config = {
    odooUrl: urlInput ? urlInput.value.trim().replace(/\/+$/, '') : '',
    apiToken: tokenInput ? tokenInput.value.trim() : '',
    fetchDays: daysInput ? parseInt(daysInput.value) || 30 : 30,
  };

  await saveConfig(config);
  state.config = config;
  showToast('Đã lưu cài đặt');
}

async function testConnection() {
  try {
    const response = await chrome.runtime.sendMessage({ type: 'HEALTH_CHECK' });
    if (response && response.success) {
      showToast('Kết nối Odoo thành công!');
    } else {
      showToast(`Lỗi: ${response?.error || 'Không thể kết nối'}`, 5000);
    }
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, 5000);
  }
}

// ====================================================================
// Bind Events
// ====================================================================
function bindEvents() {
  // Fetch button
  const btnFetch = document.getElementById('btn-fetch');
  if (btnFetch) btnFetch.addEventListener('click', startFetch);

  // Rescan button
  const btnRescan = document.getElementById('btn-rescan');
  if (btnRescan) btnRescan.addEventListener('click', () => {
    showScreen('config');
  });

  // Sync button
  const btnSync = document.getElementById('btn-sync');
  if (btnSync) btnSync.addEventListener('click', startSync);

  // Select all / Deselect all
  const btnSelectAll = document.getElementById('btn-select-all');
  const btnDeselectAll = document.getElementById('btn-deselect-all');
  if (btnSelectAll) btnSelectAll.addEventListener('click', selectAll);
  if (btnDeselectAll) btnDeselectAll.addEventListener('click', deselectAll);

  // Filters
  const filterSearch = document.getElementById('filter-search');
  const filterSource = document.getElementById('filter-source');
  const filterPdf = document.getElementById('filter-pdf');
  if (filterSearch) filterSearch.addEventListener('input', applyFilters);
  if (filterSource) filterSource.addEventListener('change', applyFilters);
  if (filterPdf) filterPdf.addEventListener('change', applyFilters);

  // Settings
  const btnSettings = document.getElementById('btn-settings');
  if (btnSettings) btnSettings.addEventListener('click', () => showScreen('settings'));

  const btnSaveSettings = document.getElementById('btn-save-settings');
  if (btnSaveSettings) btnSaveSettings.addEventListener('click', saveSettings);

  const btnTestConnection = document.getElementById('btn-test-connection');
  if (btnTestConnection) btnTestConnection.addEventListener('click', testConnection);

  const btnBackFromSettings = document.getElementById('btn-back-settings');
  if (btnBackFromSettings) btnBackFromSettings.addEventListener('click', () => {
    showScreen(state.invoices.length > 0 ? 'preview' : 'config');
  });

  // Result screen - back button
  const btnBackFromResult = document.getElementById('btn-back-result');
  if (btnBackFromResult) btnBackFromResult.addEventListener('click', () => showScreen('config'));

  // Refresh tabs button
  const btnRefreshTabs = document.getElementById('btn-refresh-tabs');
  if (btnRefreshTabs) btnRefreshTabs.addEventListener('click', checkOpenTabs);
}
