# Thiết kế tích hợp Grab e-invoice

**Tác giả:** Manus AI
**Ngày:** 2026-02-23

## 1. Tổng quan

Tài liệu này mô tả kiến trúc và các bước cần thiết để tích hợp việc lấy hóa đơn tự động từ cổng thông tin Grab e-invoice (`vn.einvoice.grab.com`) vào module `ntp_invoice_collector` của Odoo.

## 2. Phân tích hệ thống Grab e-invoice

Qua quá trình nghiên cứu, chúng tôi đã xác định các đặc điểm chính của hệ thống Grab e-invoice:

- **Nền tảng**: Đây là một cổng thông tin web (web portal) do HILO GROUP cung cấp cho Grab, không phải là một API công khai có tài liệu.
- **Xác thực**: Quá trình đăng nhập yêu cầu `Tài khoản (UserName)`, `Mật khẩu (Password)`, và một `Mã kiểm tra (CAPTCHA)`.
- **Luồng hoạt động**: 
    1. Người dùng truy cập trang đăng nhập (`/tai-khoan/dang-nhap`).
    2. Hệ thống trả về một form đăng nhập cùng với một `__RequestVerificationToken` (chống CSRF) và một ảnh CAPTCHA từ endpoint `/Captcha/Show`.
    3. Người dùng nhập thông tin và gửi form (POST) đến `/tai-khoan/dang-nhap`.
    4. Nếu thành công, người dùng được chuyển hướng đến trang quản lý hóa đơn (`/hoa-don/danh-sach`).
- **API nội bộ**: Sau khi đăng nhập, trang web sử dụng các lời gọi AJAX để tương tác với backend. Các endpoint quan trọng bao gồm:
    - `/Invoice/GetList`: Lấy danh sách hóa đơn (dạng JSON).
    - `/Invoice/DowloadData`: Tải file (PDF, XML) của một hoặc nhiều hóa đơn.

## 3. Thách thức

Thách thức lớn nhất là việc **xử lý CAPTCHA** trong một quy trình tự động. Việc sử dụng các dịch vụ giải CAPTCHA của bên thứ ba sẽ phát sinh chi phí và tăng độ phức tạp. Do đó, giải pháp đề xuất sẽ tập trung vào việc giảm thiểu sự tương tác của người dùng nhưng vẫn đảm bảo quy trình hoạt động.

## 4. Kiến trúc đề xuất

Chúng tôi sẽ áp dụng phương pháp **Web Scraping có quản lý phiên (Session-based Scraping)** kết hợp với sự hỗ trợ của người dùng để giải CAPTCHA khi cần thiết.

### 4.1. Cập nhật cấu hình (`collector_config.py`)

- Bổ sung trường `user_agent` để giả lập trình duyệt.
- Bổ sung trường `captcha_api_key` (tùy chọn) để tích hợp dịch vụ giải CAPTCHA trong tương lai.
- Mật khẩu (`api_secret`) sẽ được sử dụng cho trường `Password` của Grab.

### 4.2. Luồng lấy hóa đơn mới (`collected_invoice.py`)

Chúng tôi sẽ viết lại hàm `_fetch_grab_invoices` với logic hoàn toàn mới:

1.  **Khởi tạo phiên (Session)**: Sử dụng thư viện `requests.Session` để duy trì cookie và headers trong suốt quá trình làm việc.
2.  **Lấy trang đăng nhập**: Gửi yêu cầu GET đến `/tai-khoan/dang-nhap` để lấy `__RequestVerificationToken` và cookie của phiên.
3.  **Xử lý CAPTCHA**:
    - Tải ảnh CAPTCHA từ `/Captcha/Show`.
    - **Giải pháp 1 (Ưu tiên)**: Lưu ảnh CAPTCHA vào một trường tạm trong Odoo và tạo một `Activity` (Hành động cần làm) cho người dùng được chỉ định. Người dùng sẽ nhập mã CAPTCHA và một action sẽ được kích hoạt để tiếp tục quy trình.
    - **Giải pháp 2 (Ưu tiên - Tự động)**: Sử dụng **Google Gemini Vision API** (`gemini-1.5-flash`) để tự động đọc và giải CAPTCHA. Cần cấu hình `GEMINI_API_KEY` trong biến môi trường hoặc trường `grab_gemini_api_key` trong cấu hình collector.
4.  **Thực hiện đăng nhập**: Gửi yêu cầu POST đến `/tai-khoan/dang-nhap` với `UserName`, `Password`, `__RequestVerificationToken`, và mã CAPTCHA đã được giải.
5.  **Lấy danh sách hóa đơn**: Nếu đăng nhập thành công, gửi yêu cầu GET (hoặc POST tùy thuộc vào API) đến `/Invoice/GetList` với các tham số cần thiết (ví dụ: ngày bắt đầu, ngày kết thúc).
6.  **Xử lý dữ liệu**: Lặp qua danh sách hóa đơn nhận được (JSON), so sánh với các hóa đơn đã có trong Odoo (`external_order_id`) và tạo bản ghi `ntp.collected.invoice` mới cho các hóa đơn chưa tồn tại.
7.  **(Tùy chọn) Tải file đính kèm**: Với mỗi hóa đơn mới, gọi đến `/Invoice/DowloadData` để tải về file PDF/XML và đính kèm vào bản ghi Odoo.

### 4.3. Cập nhật Model và View

- **`collected_invoice.py`**: Bổ sung hàm `_solve_captcha_and_continue` để xử lý logic sau khi người dùng nhập mã CAPTCHA.
- **`collector_config.xml`**: Thêm các trường mới vào form view.
- **Tạo Wizard/Activity**: Tạo view cho Activity để người dùng có thể xem ảnh CAPTCHA và nhập mã.

## 5. Kế hoạch thực hiện

- **Giai đoạn 1**: Implement luồng chính với giải pháp CAPTCHA thủ công (Activity).
- **Giai đoạn 2**: Tích hợp tải file đính kèm (PDF/XML).
- **Giai đoạn 3**: Tích hợp Google Gemini Vision API để tự động giải CAPTCHA cho cả 3 hệ thống (Grab, SPV, Shinhan). ✅ **Đã hoàn thành** (phiên bản 15.0.2.1.0)

Bằng cách này, chúng ta có thể tự động hóa phần lớn quy trình, chỉ yêu cầu sự can thiệp của người dùng ở bước không thể tránh khỏi là giải CAPTCHA, giúp giảm thiểu đáng kể thời gian và công sức so với việc làm thủ công hoàn toàn.
