/**
 * content-bridge.js
 * Content script chạy trên các trang web hóa đơn.
 * Đóng vai trò cầu nối giữa trang web và background service worker.
 */

(function () {
  'use strict';

  // Xác định nguồn dựa trên URL hiện tại
  const currentUrl = window.location.href;
  let source = null;

  if (currentUrl.includes('einvoice.grab.com')) {
    source = 'grab';
  } else if (currentUrl.includes('tracuuhoadon.online')) {
    source = 'tracuu';
  } else if (currentUrl.includes('einvoice.shinhan.com.vn')) {
    source = 'shinhan';
  }

  if (!source) return;

  console.log(`[NTP E-Invoice] Content bridge loaded for: ${source}`);

  // Lắng nghe message từ background/popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'PING') {
      sendResponse({ success: true, source, url: currentUrl });
      return true;
    }

    if (message.type === 'GET_PAGE_INFO') {
      sendResponse({
        success: true,
        source,
        url: currentUrl,
        title: document.title,
        cookies: document.cookie,
      });
      return true;
    }

    if (message.type === 'INJECT_SCRAPER') {
      // Thông báo trang đã sẵn sàng
      sendResponse({ success: true, ready: true, source });
      return true;
    }

    return false;
  });

  // Thông báo cho background rằng content script đã load
  chrome.runtime.sendMessage({
    type: 'CONTENT_SCRIPT_READY',
    source,
    url: currentUrl,
  }).catch(() => {
    // Background có thể chưa sẵn sàng, bỏ qua
  });
})();
