# BÁO CÁO TIẾN ĐỘ DỰ ÁN NEARBOX MVP BACKEND
*(Cập nhật ngày 06/11/2026)*

Tài liệu này tổng hợp toàn bộ các hạng mục đã hoàn thành, các tính năng đã cài đặt và các điểm chưa thực hiện (hoặc nằm ngoài phạm vi MVP) của hệ thống **NearBox Backend**.

---

## 📌 I. TỔNG QUAN DỰ ÁN
- **Mục tiêu:** Xây dựng Backend hoàn chỉnh cho MVP nền tảng cho thuê đồ dùng ngang hàng (P2P) giữa cư dân Vinhomes Grand Park (The Rainbow, The Origami).
- **Phạm vi kỹ thuật:** Backend thuần túy (**REST API + Django Admin**). Không xây dựng Frontend, không dùng Supabase/Firebase, không tích hợp cổng thanh toán thật, không tích hợp SMS Gateway thật.
- **Công nghệ cốt lõi:** Python 3.12, Django 5, DRF, SimpleJWT, Pillow, WhiteNoise, PostgreSQL 16, pytest-django, factory-boy, Docker Compose.

---

## ✅ II. NHỮNG GÌ ĐÃ HOÀN THÀNH (DONE)

### 1. Hạ tầng & Đóng gói Docker (DevOps & Packaging)
- [x] **`docker-compose.yml`**: Thiết lập 3 dịch vụ liên kết hoàn chỉnh:
  - `db`: PostgreSQL 16 Alpine kèm healthcheck (`pg_isready`).
  - `web`: Ứng dụng Django 5 chính chạy trên Python 3.12-slim, tự động chờ db, chạy migrate, collectstatic và nạp `seed_demo`.
  - `scheduler`: Container chạy nền kiểm tra và tự động huỷ đơn quá hạn mỗi 60 giây (`expire_orders`).
- [x] **`Dockerfile` & Script khởi chạy**: Đã chuẩn hóa toàn bộ xuống dòng Unix (`LF`), cấu hình `entrypoint.sh` tự động tạo migrations khi khởi chạy lần đầu.
- [x] **`Makefile`**: Cung cấp đầy đủ các phím tắt quản trị: `up`, `down`, `restart`, `logs`, `reset`, `test`, `seed`, `shell`, `schema`, `createadmin`.
- [x] **`README.md`**: Hướng dẫn 3 dòng khởi động nhanh, bảng thông tin đăng nhập mẫu, mô tả kiến trúc và quy chuẩn nghiệp vụ.
- [x] **`.env.example` & `.dockerignore`**: Cấu hình biến môi trường mẫu, chạy được ngay cả khi không có file `.env`.

### 2. Nghiệp vụ Cốt lõi & Tính toán Tiền tệ (`apps/core/`)
- [x] **Quy chuẩn tiền tệ:** Lưu trữ toàn bộ bằng `BigIntegerField` (VND), không sử dụng số thực `float`.
- [x] **Công thức gợi ý giá:** Tự động tính 7% – 8% giá bán lẻ / ngày, làm tròn đến 1.000 VND (`round_vnd`).
- [x] **3 Bậc tiền cọc cố định:**
  - `< 1.000.000 VND`: Cọc **200.000 VND**.
  - `1.000.000 – 1.999.999 VND`: Cọc **500.000 VND**.
  - `2.000.000 – 3.000.000 VND`: Cọc **1.000.000 VND**.
- [x] **Bộ lọc chặn đăng đồ giá trị cao/đồ điện tử:** Chặn đăng sản phẩm có giá bán lẻ `> 3.000.000 VND` hoặc thuộc danh mục đồ điện tử (`electronics`) với mã lỗi chuẩn `422`.
- [x] **Quy tắc phân chia doanh thu:**
  - Phí nền tảng người thuê: 5.000 VND / đơn.
  - Hoa hồng NearBox: 15% tiền thuê.
  - Chủ đồ nhận: 85% tiền thuê.
  - Trích quỹ rủi ro: 4% doanh thu NearBox vào sổ cái.
- [x] **Xử lý lỗi thống nhất (`exceptions.py`):** Chuẩn hóa response lỗi bằng tiếng Việt kèm mã lỗi định danh (`ErrorCode`) và HTTP status tương ứng (400, 403, 409, 422).

### 3. Quản lý Người dùng & Cư dân (`apps/accounts/`)
- [x] **Custom User Model:** Định danh bằng số điện thoại (`phone`), quản lý toà nhà (S1–S10), số căn hộ, trạng thái xác minh cư dân (`is_resident_verified`), ảnh minh chứng cư dân (`resident_proof`). **Tuyệt đối không lưu số CCCD/CMND**.
- [x] **Xác thực Mock OTP:**
  - `POST /api/v1/auth/request-otp/`: Tạo mã OTP 6 số, in ra log console trong môi trường phát triển.
  - `POST /api/v1/auth/verify-otp/`: Nhận JWT tokens (`access`, `refresh`). Hỗ trợ mã bypass `000000` khi `DEBUG=True`.
- [x] **Thông tin cá nhân & Minh chứng:** `GET/PATCH /api/v1/auth/me/` và `POST /api/v1/auth/me/resident-proof/`.
- [x] **Django Admin Duyệt cư dân:** Xem trước ảnh minh chứng, action Duyệt / Từ chối cư dân hàng loạt.

### 4. Danh mục & Sản phẩm Cho thuê (`apps/catalog/`)
- [x] **4 Nhóm danh mục:** Dụng cụ sửa chữa (`repair_tools`), Vệ sinh (`cleaning`), Dã ngoại (`outdoor`), Đồ gia dụng nhỏ / làm bánh (`small_appliances`).
- [x] **Mô hình Sản phẩm (`Item`):** Tự động tính `% tiết kiệm khi thuê` (`savings_percent`), tự động gán bậc tiền cọc theo giá bán lẻ.
- [x] **Quy tắc đăng đồ:** Chỉ cư dân đã xác minh (`is_resident_verified=True`) mới có quyền đăng sản phẩm.
- [x] **Ưu tiên đồ cùng toà nhà (`Same-Building First`):** API danh sách sản phẩm `GET /api/v1/items/` tự động sắp xếp sản phẩm thuộc toà nhà của người gọi lên đầu danh sách.
- [x] **API Gợi ý giá:** `POST /api/v1/items/price-suggestion/`.
- [x] **Yêu cầu thuê đồ & Báo giá ngược:** CRUD `RentalRequest` và `POST /rental-requests/{id}/quotes/`.
- [x] **Cảnh báo Admin khi duyệt tin:** Tự động hiện cảnh báo trong Admin nếu giá > 3M hoặc danh mục điện tử.

### 5. Dịch vụ Đơn hàng & Ảnh Bàn giao (`apps/orders/`)
- [x] **Toàn bộ logic nghiệp vụ nằm tại Service Layer (`apps/orders/services.py`):** Tất cả hàm đều chạy trong `transaction.atomic()` với khoá dòng `select_for_update()`.
- [x] **Quy trình trạng thái đơn (State Machine):**
  - `pending_owner` → `awaiting_payment` → `escrow_held` → `handed_over` → `returned` → `completed` (hoặc `disputed` / `cancelled`).
  - Ghi nhật ký bất biến `OrderEvent` cho mọi lần chuyển trạng thái.
- [x] **Xử lý ảnh bàn giao bằng Pillow (`HandoverPhoto`):**
  - Tự động bóc tách toàn bộ metadata EXIF để bảo vệ quyền riêng tư.
  - Đóng dấu (watermark) mã đơn hàng và thời gian server lên ảnh.
  - Tính toán và lưu mã băm SHA-256 đối chiếu toàn vẹn dữ liệu.
- [x] **Điều kiện nghiệm thu bàn giao & trả đồ:**
  - Bàn giao tại sảnh yêu cầu phải có ảnh Check-in VÀ người thuê phải đồng ý điều khoản miễn trừ trách nhiệm pháp lý.
  - Trả đồ yêu cầu phải có ảnh Check-out trước khi chủ đồ bấm xác nhận hoàn cọc.
  - Huỷ tại sảnh (`cancel-at-lobby`): Hoàn tiền cọc và phí 100%.
- [x] **Hạn chót & Đếm ngược (`deadline_at`):** Trả về thời gian server để client hiển thị đồng hồ đếm ngược; tự động huỷ sau 15 phút nếu chủ không duyệt.

### 6. Sổ cái Escrow & Ví cư dân (`apps/escrow/`)
- [x] **Sổ cái bất biến (`LedgerEntry`):**
  - Phân loại rõ ràng 8 loại bút toán: giữ tiền thuê, giữ tiền cọc, phí nền tảng, hoàn cọc, thanh toán chủ, hoa hồng, khấu trừ cọc, quỹ rủi ro.
  - Khóa quyền sửa/xoá ở cả tầng Model (`save()`, `delete()`) lẫn Django Admin.
- [x] **Ví cư dân (`Wallet`):** API `GET /api/v1/wallet/` xem số dư tức thời, tổng thu nhập trong tháng và lịch sử 50 bút toán gần nhất.

### 7. Tranh chấp & Cổng Quản trị Concierge (`apps/disputes/`)
- [x] **Quản lý khiếu nại (`Dispute`, `DisputeLog`):** Ghi nhận lý do, bằng chứng và nhật ký phân xử.
- [x] **Phân xử tranh chấp 3 phương án:**
  1. *Hoàn cọc 100% cho người thuê*.
  2. *Khấu trừ một phần cọc bồi thường chủ đồ, phần còn lại hoàn trả người thuê*.
  3. *Khấu trừ 100% cọc bồi thường chủ đồ*.
- [x] **Admin Dashboard API:** Trả về 6 chỉ số KPI vận hành:
  - Tổng tiền cọc đang giữ trong Escrow.
  - Số đơn tạo trong ngày.
  - Số tranh chấp đang mở.
  - Thời gian bàn giao trung bình (phút).
  - Tỷ lệ hoàn cọc không khiếu nại (%).
  - Số sản phẩm hợp lệ đăng mới trong tuần.
- [x] **Django Admin Đối chiếu Ảnh:** Trang chi tiết tranh chấp hiển thị ảnh Check-in (lúc nhận) và Check-out (lúc trả) song song cạnh nhau kèm thời gian, người chụp và SHA-256.
- [x] **Xuất báo cáo CSV:** `GET /admin/export/orders.csv` và `GET /admin/export/events.csv` có gắn BOM UTF-8 mở được ngay trên Excel không bị lỗi font tiếng Việt.

### 8. Dữ liệu Mẫu Khởi tạo (`seed_demo`)
- [x] Lệnh `python manage.py seed_demo` an toàn, chạy lặp lại không trùng dữ liệu (idempotent).
- [x] Tạo sẵn 4 tài khoản mẫu:
  - Admin: `0900000000` (pass: `admin123`, OTP: `000000`).
  - Renter: `0901000001` (toà S1, OTP: `000000`).
  - Verified Owner: `0902000002` (toà S2, OTP: `000000`).
  - Pending Owner: `0903000003` (toà S3, có ảnh hợp đồng mẫu).
- [x] Tạo 12 sản phẩm thuộc đủ 4 nhóm danh mục, ảnh placeholder được vẽ trực tiếp bằng Pillow (không phụ thuộc URL ngoài).
- [x] Tạo sẵn 1 đơn tranh chấp mẫu (khoan Bosch gãy mũi) và 1 đơn trả trễ 2 giờ mẫu (thang nhôm Nikita).

### 9. Tài liệu Hợp đồng Giao tiếp & OpenAPI
- [x] **`docs/API_CONTRACT.md`**: Quy ước mã lỗi, múi giờ, định dạng tiền tệ, quy tắc hợp đồng client "Camera-only, No gallery", mã QR thanh toán.
- [x] **`docs/openapi.yaml`**: Toàn bộ 25+ REST API endpoints định dạng OpenAPI 3.0 chuẩn cho frontend dev sinh code.
- [x] **`docs/NearBox.postman_collection.json`**: Postman collection đầy đủ kịch bản kiểm thử kèm biến môi trường và tự động gán Bearer Token.

### 10. Bộ Kiểm thử Đơn vị Tự động (`tests/`)
- [x] `tests/factories.py`: Factory-boy cho User, Admin, Category, Item, Order.
- [x] `tests/test_pricing.py`: Kiểm thử gợi ý giá, bậc cọc, case bài toán mẫu 105k GMV / 20.75k doanh thu NearBox.
- [x] `tests/test_orders_lifecycle.py`: Kiểm thử vòng đời đơn, quyền hạn, ảnh bàn giao, miễn trừ trách nhiệm, tự động huỷ đơn, huỷ tại sảnh.
- [x] `tests/test_disputes.py`: Kiểm thử mở khiếu nại và 3 nhánh giải quyết cọc.
- [x] `tests/test_api_endpoints.py`: Kiểm thử OTP, bảo mật, sắp xếp cùng toà nhà, dashboard, xuất CSV.

---

## ⏳ III. NHỮNG GÌ CHƯA LÀM (HOẶC NẰM NGOÀI PHẠM VI MVP)

Dưới đây là các phần **chủ động không thực hiện** (theo đúng yêu cầu đặc tả đề bài MVP) hoặc các tính năng mở rộng dành cho các giai đoạn tiếp theo (Phase 2):

### 1. Nằm ngoài phạm vi MVP (Theo yêu cầu đề bài)
- ❌ **Giao diện người dùng (Frontend Web / Mobile App):** Dự án này là **Backend thuần túy (REST API + Django Admin)**. Không xây dựng giao diện người dùng cuối; toàn bộ việc hiển thị do client bên ngoài tích hợp thông qua OpenAPI/Postman.
- ❌ **Cổng thanh toán trực tuyến tự động (Real Payment Gateway):** Không tích hợp VNPay, MoMo, ZaloPay, ViettelMoney hay VietQR dynamic webhook. Giai đoạn MVP sử dụng cơ chế Concierge xác nhận thanh toán thủ công thông qua mã QR mock `NBX-<code_don>-<tong_tien>`.
- ❌ **Cổng gửi tin nhắn SMS thật (Real SMS Gateway):** Không kết nối Twilio, SpeedSMS, eSMS hay FPT Telecom. Mã OTP được in ra log console của server và hỗ trợ mã cố định `000000` trong môi trường `DEBUG`.
- ❌ **Celery & Redis:** Đề bài yêu cầu không sử dụng Celery/Redis để giảm thiểu tài nguyên hạ tầng. Hệ thống đã thay thế bằng cơ chế `lazy_expire_check` trên mỗi request và container scheduler chạy lệnh `expire_orders` mỗi phút.
- ❌ **Lưu trữ Căn cước công dân (CCCD):** Tuyệt đối không thiết kế trường lưu trữ hoặc yêu cầu người dùng gửi ảnh CCCD/CMND để đảm bảo quyền riêng tư và tránh rủi ro pháp lý.

### 2. Tiềm năng nâng cấp cho Giai đoạn Tiếp theo (Future Roadmap / Phase 2)
- ⚠️ **Thông báo đẩy thời gian thực (Push Notifications / WebSockets):**
  - *Hiện tại:* Client đếm ngược theo trường `deadline_at` hoặc gửi request kiểm tra định kỳ (polling).
  - *Phase 2:* Tích hợp Firebase Cloud Messaging (FCM) hoặc Django Channels / SSE để đẩy thông báo chuông tới điện thoại khi chủ đồ duyệt đơn hoặc khi có khiếu nại mới.
- ⚠️ **Hệ thống Chat nội bộ giữa Người thuê và Chủ đồ (In-app Chat):**
  - *Hiện tại:* Cư dân liên hệ qua số điện thoại hiển thị trên đơn thuê hoặc nhờ Concierge hỗ trợ tại sảnh.
  - *Phase 2:* Tích hợp kênh chat trực tiếp trong app có lưu lịch sử đính kèm ảnh bàn giao.
- ⚠️ **Lưu trữ Cloud Storage (AWS S3 / Cloudflare R2 / GCS):**
  - *Hiện tại:* Toàn bộ ảnh được lưu trong thư mục `media/` cục bộ mount qua Docker volume.
  - *Phase 2:* Chuyển sang lưu trữ S3/R2 với CDN để tăng tốc độ tải ảnh Check-in/Check-out.
- ⚠️ **Cơ chế Đánh giá & Điểm uy tín (Rating & Review System):**
  - *Hiện tại:* Độ tin cậy dựa trên badge cư dân xác minh (`is_resident_verified`) và lịch sử hoàn tất đơn.
  - *Phase 2:* Bổ sung bảng đánh giá sao (1–5 sao), review và điểm tín nhiệm cho người thuê/chủ đồ.

---

## 🎯 IV. BẢNG ĐỐI CHIẾU TIÊU CHÍ NGHIỆM THU (ACCEPTANCE CRITERIA)

| Tiêu chuẩn nghiệm thu đề bài | Trạng thái | Nơi triển khai / File minh chứng |
| :--- | :---: | :--- |
| 1. Docker `git clone` → `docker compose up` chạy ngay không cần `.env` | ✅ Đạt | `docker-compose.yml`, `Dockerfile`, `entrypoint.sh` |
| 2. Gợi ý giá 7–8%, 3 bậc cọc (200k/500k/1M), chặn đồ > 3M/điện tử | ✅ Đạt | `apps/core/constants.py`, `apps/core/utils.py` |
| 3. Tiền tệ dùng `BigIntegerField` VND, không dùng float | ✅ Đạt | Models: `catalog.Item`, `orders.Order`, `escrow.LedgerEntry` |
| 4. Không lưu CCCD, đăng nhập OTP mock, xác minh cư dân | ✅ Đạt | `apps/accounts/models.py`, `apps/accounts/views.py` |
| 5. Ảnh bàn giao Pillow bóc EXIF, đóng dấu mã đơn + giờ, SHA-256 | ✅ Đạt | `apps/orders/views.py` (`process_handover_photo`) |
| 6. Sổ cái Escrow bất biến không cho sửa/xoá | ✅ Đạt | `apps/escrow/models.py`, `apps/escrow/admin.py` |
| 7. Toàn bộ logic tại `services.py`, transaction atomic + select_for_update | ✅ Đạt | `apps/orders/services.py` |
| 8. Tự huỷ đơn quá hạn 15 phút (lazy check + scheduler) | ✅ Đạt | `expire_orders.py`, `docker/scheduler.sh` |
| 9. Django Admin Concierge: duyệt cư dân, xác nhận tiền, đối chiếu ảnh song song | ✅ Đạt | `apps/accounts/admin.py`, `apps/orders/admin.py`, `apps/disputes/admin.py` |
| 10. Lệnh nạp demo `seed_demo` idempotent, đủ 10 toà, 12 đồ, 1 tranh chấp, 1 trả trễ | ✅ Đạt | `apps/orders/management/commands/seed_demo.py` |
| 11. Cung cấp `openapi.yaml`, Postman collection, `API_CONTRACT.md` | ✅ Đạt | Thư mục `docs/` |

---
*Báo cáo được khởi tạo tự động bởi Antigravity Assistant.*
