# NearBox API Contract & Quy ước Giao thức

Tài liệu này định nghĩa hợp đồng kỹ thuật giữa NearBox Backend và các ứng dụng client (Web / Mobile).

---

## 1. Múi giờ & Định dạng Dữ liệu (Timezone & Data Formats)

- **Múi giờ chuẩn:** `Asia/Ho_Chi_Minh` (UTC+7). Mọi trường thời gian (`created_at`, `pickup_time`, `deadline_at`, `taken_at`) đều được serialize theo chuẩn ISO 8601 (ví dụ: `2026-11-06T14:30:00+07:00`).
- **Tiền tệ (Currency):** Toàn bộ số tiền đều tính bằng Đồng Việt Nam (**VND**) và được lưu trữ, truyền tải dưới dạng số nguyên (`BigIntegerField`, tuyệt đối không dùng số thực `float`).
  - Ví dụ: `70000` thay vì `70000.0`.
- **Định dạng URL Ảnh:** Mọi URL ảnh trả về đều là URL tuyệt đối dựa trên cấu hình `PUBLIC_BASE_URL` (ví dụ: `http://localhost:8000/media/...`).

---

## 2. Quy ước Phân trang (Pagination)

Các API danh sách (`GET /api/v1/items/`, `GET /api/v1/orders/`, v.v.) tuân theo chuẩn Page Number Pagination của Django REST Framework:

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/items/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

Tham số truy vấn: `?page=1&page_size=20`.

---

## 3. Quy ước Lỗi (Error Conventions)

Tất cả các phản hồi lỗi từ hệ thống đều tuân thủ cấu trúc chuẩn, thông điệp hướng tới người dùng bằng tiếng Việt và mã lỗi ổn định để client xử lý logic:

```json
{
  "error": true,
  "code": "ORDER_INVALID_STATE",
  "message": "Không thể chuyển đơn hàng từ 'Chờ chủ duyệt' sang 'Đã giao'."
}
```

### Bảng mã lỗi chuẩn (`code`):

| Mã lỗi (`code`) | HTTP Status | Diễn giải |
| :--- | :--- | :--- |
| `ORDER_INVALID_STATE` | `409 Conflict` | Trạng thái chuyển đổi không hợp lệ trong quy trình đơn hàng |
| `ITEM_BLOCKED_HIGH_VALUE` | `422 Unprocessable Entity` | Sản phẩm có giá bán lẻ vượt quá ngưỡng tối đa cho phép (3,000,000 VND) |
| `ITEM_BLOCKED_CATEGORY` | `422 Unprocessable Entity` | Danh mục sản phẩm bị chặn (ví dụ: đồ điện tử giá trị cao) |
| `OWNER_NOT_VERIFIED` | `403 Forbidden` / `422` | Chủ đồ chưa được xác minh cư dân Vinhomes Grand Park |
| `MISSING_CHECKIN_PHOTO` | `422 Unprocessable Entity` | Chưa có ảnh chụp lúc bàn giao (Check-in) tại sảnh |
| `MISSING_CHECKOUT_PHOTO` | `422 Unprocessable Entity` | Chưa có ảnh chụp lúc trả đồ (Check-out) tại sảnh |
| `MISSING_WAIVER_CONSENT` | `422 Unprocessable Entity` | Người thuê chưa bấm đồng ý điều khoản miễn trừ trách nhiệm pháp lý |
| `INVALID_OTP` | `400 Bad Request` | Mã OTP không chính xác hoặc đã hết hạn |
| `IMAGE_TOO_LARGE` | `400 Bad Request` | Dung lượng file ảnh vượt quá giới hạn (tối đa 5MB) |
| `ITEM_NOT_AVAILABLE` | `400 Bad Request` | Sản phẩm đang không ở trạng thái sẵn sàng cho thuê |
| `PERMISSION_DENIED` | `403 Forbidden` | Không có quyền thao tác trên tài nguyên này |

---

## 4. Hợp đồng Chụp ảnh Bàn giao (Camera-Only & Photo Upload Contract)

### Phía Client (Frontend Web / Mobile App):
1. **Camera-Only, No Gallery:** Do trình duyệt và API web không thể ép buộc 100% việc cấm chọn từ thư viện ảnh ở mức server, client **phải** cấu hình trường nhập ảnh camera trực tiếp:
   - Trên HTML: `<input type="file" accept="image/*" capture="environment" />`
   - Trên React Native / Flutter: Cấu hình `ImagePicker.openCamera()` thay vì `openPicker()`.
2. **Dung lượng:** Giới hạn tối đa **5MB** cho mỗi file ảnh. Định dạng hợp lệ: `image/jpeg`, `image/png`.
3. **Thời điểm upload:** Ảnh bàn giao phải được chụp và tải lên ngay tại thời điểm diễn ra giao dịch ở sảnh sảnh tòa nhà (7:30–8:30 hoặc 18:30–20:30).

### Phía Server (Backend xử lý tự động):
1. **Server Timestamp (`taken_at`):** Server tự gán thời gian chụp dựa trên đồng hồ server tại thời điểm nhận ảnh, không dùng timestamp từ EXIF của thiết bị client.
2. **Xóa EXIF:** Toàn bộ dữ liệu EXIF (GPS, thông tin thiết bị gốc) được bóc tách và loại bỏ hoàn toàn bằng Pillow để bảo mật quyền riêng tư.
3. **Đóng dấu bản quyền & xác thực (Watermark):** Server tự động vẽ chữ đè lên ảnh bao gồm **Mã đơn hàng** và **Thời gian chụp** (ví dụ: `NBX-A1B2C3 | 2026-11-06 14:35:10`).
4. **Băm SHA-256:** Server lưu trữ mã băm SHA-256 của file ảnh gốc phục vụ đối chiếu toàn vẹn dữ liệu khi có tranh chấp.

---

## 5. Xác thực & Đăng nhập (Authentication Flow)

NearBox không sử dụng mật khẩu tài khoản đối với cư dân thông thường. Quy trình đăng nhập gồm 2 bước:
1. `POST /api/v1/auth/request-otp/` với `{"phone": "0901000001"}`:
   - Hệ thống tạo mã OTP 6 chữ số (trong môi trường phát triển sẽ in trực tiếp ra log console).
2. `POST /api/v1/auth/verify-otp/` với `{"phone": "0901000001", "otp": "000000"}`:
   - Trong môi trường `DEBUG=True`, mã OTP `000000` luôn được chấp nhận để thuận tiện cho việc test và demo.
   - Phản hồi trả về cặp JWT Token: `access` và `refresh`.
3. Khi gọi các API yêu cầu xác thực, gửi kèm Header:
   `Authorization: Bearer <access_token>`

---

## 6. Mô phỏng Chuyển khoản Thanh toán (Payment QR Mock)

Hệ thống NearBox MVP không tích hợp cổng thanh toán thực tế của bên thứ ba.
- Khi đơn hàng chuyển sang trạng thái `awaiting_payment`, trường `qr_content` trả về chuỗi nội dung chuyển khoản theo cú pháp:
  `NBX-<order_code>-<total_amount>`
  (Ví dụ: `NBX-A1B2C3-275000`)
- Renter quét mã hoặc chuyển khoản với nội dung này.
- Concierge (Admin) kiểm tra tài khoản ngân hàng và bấm **Xác nhận thanh toán** qua Django Admin hoặc endpoint `POST /api/v1/admin/orders/{id}/confirm-payment/`.

---

## 7. Cơ chế Tự động Huỷ đơn Quá hạn (15-Minute Timeout)

- Khi đơn hàng ở trạng thái `pending_owner` (Chờ chủ đồ duyệt), hệ thống tự động gán `deadline_at` = thời gian hiện tại + 15 phút.
- **Lazy Check:** Khi client gọi bất kỳ API nào liên quan đến đơn hàng (`GET /orders/{id}/`, `POST /orders/{id}/approve/`, v.v.), server sẽ kiểm tra nếu thời gian đã quá `deadline_at` thì đơn hàng tự động chuyển sang trạng thái `cancelled`.
- **Background Cron Scheduler:** Container `scheduler` chạy lệnh `python manage.py expire_orders` định kỳ mỗi phút một lần để huỷ đơn quá hạn ngay cả khi người dùng không tương tác.
