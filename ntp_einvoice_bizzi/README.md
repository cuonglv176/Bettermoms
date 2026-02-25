# NTP E-Invoice Bizzi Staging - Odoo 15 Module

Module Odoo 15 tiếp nhận hóa đơn điện tử từ Chrome/Edge Extension, lưu trữ staging và đẩy sang Bizzi.

## Cài đặt Module

### Bước 1: Copy module vào addons path

```bash
# Copy module vào thư mục addons của Odoo
cp -r ntp_einvoice_bizzi /path/to/odoo/addons/

# Hoặc nếu dùng custom addons path
cp -r ntp_einvoice_bizzi /opt/odoo/custom-addons/
```

### Bước 2: Cập nhật addons path trong odoo.conf

```ini
[options]
addons_path = /opt/odoo/addons,/opt/odoo/custom-addons
```

### Bước 3: Cài đặt module

```bash
# Restart Odoo và update module list
sudo systemctl restart odoo

# Hoặc chạy lệnh update
python3 odoo-bin -d ntp -u ntp_einvoice_bizzi --stop-after-init
```

### Bước 4: Cài đặt qua giao diện

1. Vào **Odoo → Apps → Update Apps List**
2. Tìm kiếm "NTP E-Invoice Bizzi"
3. Nhấn **Install**

## Cấu hình sau khi cài đặt

### 1. Cấu hình Bizzi API

Vào **Cài đặt → NTP E-Invoice Bizzi**:
- **Bizzi API URL**: `https://api.bizzi.vn/v1` (liên hệ Bizzi để xác nhận)
- **Bizzi API Key**: Lấy từ Bizzi portal
- **Bizzi Company Code**: Mã công ty trên Bizzi

### 2. Tạo Extension API Token

1. Vào **Cài đặt → NTP E-Invoice Bizzi**
2. Nhấn **"Tạo Token mới"**
3. Copy token và dán vào cài đặt Chrome Extension

### 3. Kích hoạt Cron Jobs

Vào **Cài đặt → Kỹ thuật → Tác vụ định kỳ**:
- **"E-Invoice Bizzi: Tự động đẩy staging sang Bizzi"**: Bật và cấu hình interval (VD: 30 phút)
- **"E-Invoice Bizzi: Cập nhật trạng thái từ Bizzi"**: Bật nếu cần poll status

## Phân quyền

| Nhóm | Quyền |
|------|-------|
| Người dùng E-Invoice | Xem danh sách, xem chi tiết |
| Quản lý E-Invoice | Toàn quyền, cấu hình, đẩy Bizzi |

## API Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/api/einvoice/health` | Kiểm tra kết nối |
| POST | `/api/einvoice/staging/create` | Tạo một staging |
| POST | `/api/einvoice/staging/batch` | Tạo nhiều staging |
| GET | `/api/einvoice/staging/list` | Danh sách staging |
| POST | `/api/einvoice/staging/{id}/push-bizzi` | Đẩy sang Bizzi |

## Xử lý sự cố

### Lỗi "Token không hợp lệ"
- Kiểm tra token trong Extension khớp với token trong Odoo Settings
- Tạo token mới và cập nhật lại Extension

### Lỗi "Bizzi API Key chưa cấu hình"
- Vào Cài đặt → NTP E-Invoice Bizzi → Nhập Bizzi API Key

### Hóa đơn không đẩy được sang Bizzi
- Kiểm tra Bizzi API URL và API Key
- Xem log chi tiết trong cột "Log phản hồi Bizzi" trên form view
- Nhấn "Reset về Nháp" và thử lại
