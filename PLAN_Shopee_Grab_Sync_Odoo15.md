### Kế hoạch triển khai (Odoo 15) — Shopee/Grab: Hóa đơn, Chuẩn hóa địa chỉ, Liên kết đơn hàng

Mục tiêu: Giải quyết 3 vấn đề hiện tại dựa trên code sẵn có để giảm thao tác thủ công, đảm bảo dữ liệu chuẩn và có thể kiểm thử, vận hành ổn định.

Phạm vi repo: D:\Jeisys (ưu tiên các addon Odoo 15, đặc biệt thư mục Odoo-Omoda\addons_crm\odoo_shopee_connector)

1) Vấn đề và bối cảnh hiện tại
- Hóa đơn (invoice) đang phải tải thủ công từ Grab, Shopee để import lên hệ thống.
- Trường địa chỉ từ Shopee trả về đang là tên tỉnh/thành cũ (trước khi sáp nhập/gộp), trong khi trên hệ thống cần địa chỉ theo danh mục tỉnh/thành mới của Việt Nam.
- Đơn hàng Shopee đang nhập tay và ghi chú thủ công mối liên hệ giữa mã đơn trên Odoo và mã đơn trên Shopee.

2) Mã sẵn có có thể tận dụng
- Shopee connector hiện diện: D:\Jeisys\Odoo-Omoda\addons_crm\odoo_shopee_connector
  - Có components importer/binder/mapper cho sản phẩm, đơn hàng, đối tác, danh mục…
  - Khả năng binding (liên kết external ID <-> Odoo ID) thông qua “binder” đã có nền tảng để lưu x_ref Shopee.
- Chưa thấy module dành riêng cho Grab. Với điều kiện hiện tại, nên triển khai đường nhập CSV/XLSX trước (dễ triển khai, không lệ thuộc API/cred) và cân nhắc API/email ingest ở giai đoạn sau.

3) Giải pháp tổng thể theo 3 hướng
3.1. Import hóa đơn Grab/Shopee (ưu tiên Grab CSV/XLSX, Shopee nếu có export)
- Tạo addon mới: ntp_invoice_importer
  - Wizard import CSV/XLSX: mẫu cột cho Grab và Shopee (template đi kèm). Cho phép map cột linh hoạt (partner, số hóa đơn, ngày, dòng hàng, thuế, số tiền, mã hàng).
  - Valitation: kiểm tra bắt buộc (partner, ngày, tổng tiền); khớp sản phẩm theo SKU/internal ref; khớp thuế theo mã/tỷ lệ; tạo account.move (type customer invoice) ở trạng thái draft.
  - Ghi nhận nguồn (x_marketplace='grab'/'shopee'), x_external_invoice_id để truy vết; ràng buộc unique (marketplace + external_invoice_id).
  - Nhật ký import (log) và báo cáo lỗi (downloadable CSV lỗi chưa import).
  - Tùy chọn: ghép partner theo số điện thoại/email; nếu không khớp thì tạo partner mới ở trạng thái nháp/flag “cần rà soát”.
- Giai đoạn 2 (tùy chọn):
  - Email listener: đọc mailbox chuyên dụng, trích file đính kèm Grab invoice (PDF/CSV), chuyển đổi sang dữ liệu import; lưu đính kèm vào bill/invoice.
  - API client (nếu Grab/Shopee cung cấp) dùng system parameters để cấu hình tokens/keys; cron định kỳ kéo hóa đơn mới.

3.2. Chuẩn hóa địa chỉ VN (tỉnh/thành sau gộp) áp dụng cho dữ liệu từ Shopee
- Tạo addon mới: ntp_vn_address_normalizer
  - Data mapping: bảng alias cho tỉnh/thành (old_name, aliases -> res.country.state mới). Nguồn: danh mục state tiêu chuẩn trong hệ thống + file alias đi kèm.
  - Service normalize_address(vals): nhận dict địa chỉ (name, phone, street, city, state_text, zip, country) trả về vals đã gán state_id theo chuẩn. Lưu nguyên bản chuỗi cũ vào trường note/legacy_state_name để đối soát.
  - Hook vào: res.partner create/write; Shopee importer mapper (đối tác và đơn hàng) để tự động chuẩn hóa khi nhận dữ liệu mới.
  - Wizard backfill: quét partner/order hiện có, cập nhật state_id từ city/state_text cũ theo alias. Có chế độ dry-run + báo cáo.
  - Xử lý mơ hồ: nếu nhiều alias khớp, đánh dấu “ambiguous” để người dùng chọn; ghi log chi tiết.

3.3. Tự động đồng bộ đơn Shopee + ràng buộc mã
- Tận dụng odoo_shopee_connector hiện có, bổ sung:
  - Trường hiển thị trên sale.order: x_shopee_order_id (indexed), x_marketplace (selection), x_external_ref_url.
  - Ràng buộc unique trên (x_marketplace, x_shopee_order_id).
  - Trong importer/mapper: luôn điền x_shopee_order_id từ Shopee order_sn và thiết lập binding bằng binder có sẵn.
  - Áp dụng normalize_address vào mapper đối tác và địa chỉ giao hàng.
  - Cron định kỳ: kéo đơn mới/cập nhật trạng thái; retry policy khi lỗi.
  - UI: hành động “Đồng bộ đơn Shopee” thủ công từ backend, smart button mở liên kết Shopee.

4) Trường dữ liệu bổ sung (đề xuất)
- sale.order:
  - x_marketplace = Selection([('shopee','Shopee'), ('grab','Grab')])
  - x_shopee_order_id = Char(index=True)
  - x_external_ref_url = Char
- account.move:
  - x_marketplace = Selection như trên
  - x_external_invoice_id = Char(index=True)
  - x_source_channel = Char
- Ràng buộc:
  - SQL/ORM unique: (x_marketplace, x_shopee_order_id) trên sale.order; (x_marketplace, x_external_invoice_id) trên account.move.

5) Test cases (Odoo 15)
5.1. Unit tests — Address Normalizer
- Exact match: "Thành phố Hồ Chí Minh" -> state_id=HCM.
- Alias cũ: "Sài Gòn" -> state_id=HCM.
- Tỉnh sáp nhập: tên cũ -> tỉnh mới theo bảng alias.
- Không khớp: state_id không set, gắn legacy_state_name, raise warning flag.
- Mơ hồ (2 alias khớp): đánh dấu ambiguous, không auto set, yêu cầu người dùng chọn thủ công.

5.2. Unit tests — Importer/Mapper
- Shopee order partner mapping: áp dụng normalize_address trước khi tạo partner; kiểm tra state_id được set.
- Duplicate protection: nhập lại cùng shopee_order_id => không tạo đơn trùng; cập nhật trạng thái/ghi log.
- Invoice importer CSV: tạo account.move draft, khớp thuế theo tỷ lệ, khớp SKU thành product_id; mismatch báo lỗi đúng dòng.

5.3. Integration (HttpCase/TransactionCase)
- Shopee order sync flow: gọi component importer với payload giả lập -> tạo sale.order, set x_shopee_order_id, binding tồn tại, địa chỉ chuẩn hóa.
- CSV invoice import wizard: upload file mẫu Grab -> tạo 1 hóa đơn draft với dòng đúng số lượng/đơn giá/tax; tổng tiền khớp.
- Backfill wizard address: dry-run trả báo cáo; chạy thật cập nhật N partner/order, log số lượng cập nhật/skip.

5.4. Hiệu năng
- Batch 1.000 dòng invoice CSV: thời gian import < X phút (tùy hạ tầng), không N+1 (prefetch fields, search_read theo lô). 
- Cron Shopee: xử lý phân trang API, giới hạn batch size, retry khi rate limit.

6) Kế hoạch triển khai theo mốc
- M1: ntp_vn_address_normalizer
  - Data alias + service normalize + hook partner + wizard backfill + tests cơ bản.
- M2: Tăng cường Shopee connector
  - Thêm trường x_* trên sale.order; cập nhật mapper dùng normalize_address; cron + action thủ công; tests.
- M3: ntp_invoice_importer
  - Wizard CSV/XLSX; template Grab/Shopee; validations; ràng buộc unique; log/report; tests.
- M4 (tùy chọn): Email/API ingest cho Grab; lưu đính kèm; monitor.

7) Cấu hình và vận hành
- System Parameters: bật/tắt marketplace, cron interval, default journals/taxes, mapping cột import.
- Quyền truy cập: chỉ nhóm Kế toán/Marketplace Manager được import/chạy cron.
- Nhật ký: _logger theo module, tránh log dữ liệu nhạy cảm; báo cáo import/export tải về được.

8) Rủi ro và giảm thiểu
- Sai mapping tỉnh: luôn giữ legacy_state_name để truy vết, wizard chỉnh tay mơ hồ.
- Trùng đơn/hóa đơn: unique constraints + upsert logic theo external_id.
- API thay đổi (Shopee/Grab): cô lập logic qua components/service + config phiên bản.

9) Tiêu chí nghiệm thu (Acceptance)
- 100% đơn Shopee mới tự đồng bộ về Odoo, có x_shopee_order_id và binding; địa chỉ state_id chuẩn.
- Import 100% file CSV Grab mẫu tạo hóa đơn draft hợp lệ; lỗi được báo rõ từng dòng.
- Backfill địa chỉ cập nhật ≥ 95% bản ghi có thể mapping, phần còn lại flagged để xử lý tay.

10) Công việc chi tiết (checklist triển khai)
- [ ] Tạo addon ntp_vn_address_normalizer (models, data alias, wizard, tests)
- [ ] Bổ sung x_* fields và unique constraints trên sale.order/account.move
- [ ] Chèn normalize vào Shopee mapper; thêm cron + action thủ công
- [ ] Tạo addon ntp_invoice_importer (wizard CSV/XLSX, validations, report, tests)
- [ ] Tài liệu hướng dẫn người dùng + template CSV/XLSX

Phụ lục: Gợi ý cấu trúc file alias tỉnh/thành
- vn_state_aliases.csv: old_name,alias,new_state_code,new_state_name
- Ví dụ: "Sài Gòn", "TPHCM", HCM, "Thành phố Hồ Chí Minh"
