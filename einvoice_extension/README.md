# NTP E-Invoice Fetcher - Chrome/Edge Extension

Extension tự động lấy hóa đơn điện tử từ **Grab**, **SPV Tracuuhoadon**, **Shinhan Bank** và đồng bộ vào Odoo 15.

## Cài đặt Extension

### Bước 1: Tải source code

```bash
git clone https://github.com/cuonglv176/Bettermoms.git
```

### Bước 2: Mở Chrome/Edge Extension Manager

- **Chrome**: Truy cập `chrome://extensions/`
- **Edge**: Truy cập `edge://extensions/`

### Bước 3: Bật Developer Mode

- Bật công tắc **"Developer mode"** (góc trên bên phải)

### Bước 4: Load Extension

- Nhấn **"Load unpacked"**
- Chọn thư mục `Bettermoms/einvoice_extension/`
- Extension sẽ xuất hiện trong danh sách

### Bước 5: Cấu hình Extension

1. Nhấn icon Extension trên thanh công cụ
2. Nhấn **⚙️ Cài đặt**
3. Nhập:
   - **Odoo Server URL**: `http://your-odoo-server:8069`
   - **API Token**: Lấy từ Odoo → Cài đặt → NTP E-Invoice Bizzi → Tạo Token mới
4. Nhấn **Kiểm tra kết nối** để xác nhận
5. Nhấn **Lưu cài đặt**

## Sử dụng

1. **Cấu hình**: Nhập số ngày cần lấy (VD: 30), chọn nguồn dữ liệu
2. **Quét**: Nhấn "Bắt đầu quét dữ liệu" - Extension sẽ tự động đăng nhập và lấy dữ liệu
3. **Kiểm duyệt**: Xem danh sách hóa đơn, tick chọn các hóa đơn cần đồng bộ
4. **Đồng bộ**: Nhấn "Đồng bộ lên Hệ thống" để đẩy vào Odoo

## Nguồn dữ liệu

| Nguồn | URL |
|-------|-----|
| Grab | https://vn.einvoice.grab.com |
| SPV Tracuuhoadon | https://spv.tracuuhoadon.online |
| Shinhan Bank | https://einvoice.shinhan.com.vn |

## Lưu ý

- Extension cần quyền truy cập vào 3 website trên để hoạt động
- File PDF được tải về và mã hóa Base64 trước khi gửi lên Odoo
- Hóa đơn trùng lặp (cùng số HĐ + MST NCC) sẽ bị bỏ qua tự động
