/**
 * shinhan-interceptor.js
 * CHẠY TRONG MAIN WORLD (page context) - cùng context với Angular.
 * 
 * Mục đích: Override các hàm download của browser để bắt file PDF/XML
 * khi Angular trigger download, thay vì để browser tải file về máy.
 * 
 * Giao tiếp với content script (isolated world) qua CustomEvent:
 * - Main world dispatch: 'ntp-file-intercepted' (khi bắt được file)
 * - Content script dispatch: 'ntp-request-download' (khi cần trigger download)
 * - Content script dispatch: 'ntp-clear-intercepted' (khi cần xóa cache)
 * 
 * QUAN TRỌNG: File này PHẢI được khai báo với world: "MAIN" trong manifest.json
 */

(function () {
  'use strict';

  // Kiểm tra chỉ chạy trên trang Shinhan
  if (!window.location.hostname.includes('shinhan.com.vn')) return;

  console.log('[NTP Interceptor] Installing in MAIN world on:', window.location.href);

  // ============================================================
  // Storage cho intercepted files
  // ============================================================
  const interceptedFiles = [];

  // ============================================================
  // Interceptor 1: Override URL.createObjectURL
  // Bắt khi Angular tạo Blob URL cho download
  // ============================================================
  const origCreateObjectURL = URL.createObjectURL.bind(URL);
  URL.createObjectURL = function (obj) {
    const blobUrl = origCreateObjectURL(obj);

    if (obj instanceof Blob && obj.size > 100) {
      const type = obj.type || '';
      console.log(`[NTP Interceptor] Blob URL created: type="${type}", size=${obj.size}`);

      // Đọc blob data ngay lập tức
      const reader = new FileReader();
      reader.onload = function () {
        const base64 = reader.result.split(',')[1];
        const fileType = (type.includes('xml') || type.includes('text/xml')) ? 'xml' : 'pdf';
        
        const fileData = {
          type: fileType,
          base64: base64,
          blobUrl: blobUrl,
          size: obj.size,
          contentType: type,
          timestamp: Date.now(),
          filename: null,
        };
        
        interceptedFiles.push(fileData);
        console.log(`[NTP Interceptor] Captured ${fileType}: size=${base64.length}, total files=${interceptedFiles.length}`);
      };
      reader.readAsDataURL(obj);
    }

    return blobUrl;
  };

  // ============================================================
  // Interceptor 2: Override HTMLAnchorElement.prototype.click
  // Chặn TẤT CẢ <a>.click() có blob: href → ngăn download về máy
  // ============================================================
  const origAnchorClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    const href = this.href || '';
    const download = this.download || this.getAttribute('download') || '';

    if (href.startsWith('blob:') && download) {
      console.log(`[NTP Interceptor] BLOCKED <a>.click() download: "${download}", href="${href}"`);

      // Tìm file đã capture từ Blob URL
      const captured = interceptedFiles.find(f => f.blobUrl === href);
      if (captured) {
        captured.filename = download;
        if (download.toLowerCase().endsWith('.xml')) captured.type = 'xml';
        else if (download.toLowerCase().endsWith('.pdf')) captured.type = 'pdf';
        
        console.log(`[NTP Interceptor] Matched file: "${download}" → ${captured.type}, base64 size=${captured.base64?.length || 0}`);
        
        // Thông báo cho content script (isolated world)
        window.dispatchEvent(new CustomEvent('ntp-file-intercepted', {
          detail: {
            type: captured.type,
            base64: captured.base64,
            filename: captured.filename,
            size: captured.size,
            timestamp: captured.timestamp,
          }
        }));
      } else {
        console.warn(`[NTP Interceptor] Blob URL not found in cache, fetching fallback...`);
        // Fallback: đọc blob từ URL
        fetch(href).then(r => r.blob()).then(blob => {
          const reader = new FileReader();
          reader.onload = function () {
            const base64 = reader.result.split(',')[1];
            const fileType = download.toLowerCase().endsWith('.xml') ? 'xml' : 'pdf';
            
            const fileData = {
              type: fileType,
              base64: base64,
              filename: download,
              size: blob.size,
              timestamp: Date.now(),
            };
            interceptedFiles.push(fileData);
            
            window.dispatchEvent(new CustomEvent('ntp-file-intercepted', {
              detail: fileData
            }));
            
            console.log(`[NTP Interceptor] Fallback captured: "${download}" → ${fileType}`);
          };
          reader.readAsDataURL(blob);
        }).catch(e => {
          console.warn('[NTP Interceptor] Fallback fetch failed:', e);
        });
      }

      // KHÔNG gọi click gốc → ngăn download về máy
      // Cleanup blob URL sau 3 giây
      setTimeout(() => {
        try { URL.revokeObjectURL(href); } catch (e) { /* ignore */ }
      }, 3000);
      return;
    }

    // Cho các link bình thường, gọi click gốc
    return origAnchorClick.call(this);
  };

  // ============================================================
  // Interceptor 3: Override window.open (nếu Angular mở tab mới)
  // ============================================================
  const origWindowOpen = window.open;
  window.open = function (url, ...args) {
    if (url && typeof url === 'string' && url.startsWith('blob:')) {
      console.log(`[NTP Interceptor] BLOCKED window.open(blob:...)`);
      fetch(url).then(r => r.blob()).then(blob => {
        const reader = new FileReader();
        reader.onload = function () {
          const base64 = reader.result.split(',')[1];
          const fileData = {
            type: 'pdf',
            base64: base64,
            size: blob.size,
            timestamp: Date.now(),
          };
          interceptedFiles.push(fileData);
          window.dispatchEvent(new CustomEvent('ntp-file-intercepted', {
            detail: fileData
          }));
        };
        reader.readAsDataURL(blob);
      }).catch(() => {});
      return null;
    }
    return origWindowOpen.call(this, url, ...args);
  };

  // ============================================================
  // Interceptor 4: Override document.createElement cho <a> tag
  // Bắt khi Angular tạo <a> element mới cho download
  // ============================================================
  const origCreateElement = document.createElement.bind(document);
  document.createElement = function (tagName, options) {
    const element = origCreateElement(tagName, options);
    
    if (tagName.toLowerCase() === 'a') {
      // Override click trên element mới tạo
      const origElClick = element.click.bind(element);
      element.click = function () {
        const href = element.href || '';
        const download = element.download || element.getAttribute('download') || '';
        
        if (href.startsWith('blob:') && download) {
          console.log(`[NTP Interceptor] BLOCKED new <a>.click(): "${download}"`);
          
          const captured = interceptedFiles.find(f => f.blobUrl === href);
          if (captured) {
            captured.filename = download;
            if (download.toLowerCase().endsWith('.xml')) captured.type = 'xml';
            else if (download.toLowerCase().endsWith('.pdf')) captured.type = 'pdf';
            
            window.dispatchEvent(new CustomEvent('ntp-file-intercepted', {
              detail: {
                type: captured.type,
                base64: captured.base64,
                filename: captured.filename,
                size: captured.size,
                timestamp: captured.timestamp,
              }
            }));
          }
          
          setTimeout(() => {
            try { URL.revokeObjectURL(href); } catch (e) { /* ignore */ }
          }, 3000);
          return;
        }
        
        return origElClick();
      };
    }
    
    return element;
  };

  // ============================================================
  // Lắng nghe yêu cầu từ content script
  // ============================================================
  
  // Yêu cầu xóa cache
  window.addEventListener('ntp-clear-intercepted', () => {
    interceptedFiles.length = 0;
    console.log('[NTP Interceptor] Cache cleared');
  });

  // Yêu cầu lấy số file đã capture
  window.addEventListener('ntp-get-file-count', () => {
    window.dispatchEvent(new CustomEvent('ntp-file-count-response', {
      detail: { count: interceptedFiles.length }
    }));
  });

  console.log('[NTP Interceptor] All interceptors installed in MAIN world ✓');
  console.log('[NTP Interceptor] Interceptors: createObjectURL, AnchorClick, window.open, createElement');

})();
