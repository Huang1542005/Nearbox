# NearBox — Nền tảng Cho thuê Đồ dùng Ngang hàng Cư dân (P2P Rental MVP)

NearBox là nền tảng cho thuê đồ dùng ngang hàng (P2P) dành riêng cho cư dân Vinhomes Grand Park (TP. Thủ Đức, TP.HCM), tập trung tại phân khu The Rainbow và The Origami. Cư dân nhận đồ trực tiếp từ hàng xóm tại sảnh tòa nhà trong vòng 5–15 phút thay vì chờ giao hàng thương mại điện tử hoặc tốn 50–100k tiền ship.

---

## 🚀 Khởi động Nhanh trong 3 Bước (3-Line Quickstart)

Bạn chỉ cần cài đặt **Docker** & **Docker Compose**. **Không cần** cài đặt Python, pip hay PostgreSQL trên máy:

```bash
git clone https://github.com/your-org/nearbox-backend.git
cd nearbox-backend
docker compose up -d --build
```

- **Swagger UI (Tài liệu API tương tác):** [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- **Django Admin (Công cụ vận hành Concierge):** [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **OpenAPI Schema:** [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

---

## 👥 Bảng Tài khoản Thử nghiệm (Seed Demo Accounts)

Sau khi container khởi động, lệnh `seed_demo` tự động chạy tạo sẵn các tài khoản mẫu sau:

| Số điện thoại | Vai trò | Trạng thái cư dân | Toà nhà | Căn hộ | Mã OTP đăng nhập (DEBUG) | Mật khẩu Admin Web |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0900000000` | **Concierge / Superadmin** | Đã xác minh | S1 | 1001 | `000000` | `admin123` |
| `0901000001` | **Người thuê (Renter)** | Đã xác minh | S1 | 0802 | `000000` | - |
| `0902000002` | **Chủ đồ (Verified Owner)** | Đã xác minh | S2 | 1205 | `000000` | - |
| `0903000003` | **Chủ đồ chờ duyệt (Pending)** | Chưa xác minh (có ảnh minh chứng) | S3 | 0410 | `000000` | - |

*(Lưu ý: Mọi số điện thoại khi đăng nhập đều có thể dùng mã OTP `000000` trong môi trường DEBUG; mã OTP ngẫu nhiên thực tế cũng được in ra console container)*.

---

## 📦 Kiến trúc Hệ thống

```
nearbox-backend/
├── docker-compose.yml       # 3 dịch vụ: db (PostgreSQL 16), web (Django 5), scheduler (expire_orders)
├── Dockerfile               # Python 3.12-slim
├── Makefile                 # Các lệnh make up, test, seed, reset...
├── apps/
│   ├── core/                # Hằng số kinh doanh, công thức tính tiền, mã lỗi tiếng Việt
│   ├── accounts/            # Custom User (USERNAME_FIELD=phone), xác thực OTP, duyệt cư dân (không lưu CCCD)
│   ├── catalog/             # Danh mục, Sản phẩm (gợi ý giá 7-8%, chặn đồ > 3M), Yêu cầu thuê & Báo giá
│   ├── orders/              # Quản lý vòng đời đơn, nhật ký trạng thái (OrderEvent), ảnh bàn giao Pillow EXIF-strip
│   ├── escrow/              # Sổ cái giao dịch bất biến (LedgerEntry: chỉ thêm, không sửa/xoá), Ví cư dân (Wallet)
│   └── disputes/            # Quản lý tranh chấp, đối chiếu ảnh Check-in/Check-out, phân xử hoàn tiền/khấu trừ
├── docs/
│   ├── API_CONTRACT.md      # Quy ước giao thức, mã lỗi, timezone, camera contract
│   ├── openapi.yaml         # Đặc tả OpenAPI 3.0 xuất sẵn cho Frontend
│   └── NearBox.postman_collection.json # Bộ sưu tập Postman hoàn chỉnh
└── tests/                   # Bộ kiểm thử pytest bao phủ 100% nghiệp vụ cốt lõi
```

---

## ⚖️ Quy tắc Nghiệp vụ Trọng tâm

1. **Gợi ý giá thuê:** 7–8% giá bán lẻ / ngày, làm tròn đến 1.000 VND.
2. **3 Bậc tiền cọc cố định:**
   - Giá bán lẻ < 1.000.000 VND: **200.000 VND**.
   - 1.000.000 – 1.999.999 VND: **500.000 VND**.
   - 2.000.000 – 3.000.000 VND: **1.000.000 VND**.
3. **Quy tắc chặn đăng:** Sản phẩm có giá bán lẻ > 3.000.000 VND hoặc thuộc danh mục đồ điện tử giá trị cao (`electronics`) sẽ bị từ chối với lỗi 422.
4. **Phân chia doanh thu:**
   - Phí nền tảng người thuê: 5.000 VND / đơn.
   - Hoa hồng NearBox: 15% tiền thuê. Chủ đồ nhận: 85% tiền thuê.
   - Quỹ rủi ro: 4% doanh thu NearBox được trích riêng vào sổ cái.
5. **Tiền tệ:** Toàn bộ số tiền đều dùng `BigIntegerField` (VND), không bao giờ dùng `float`.
6. **Bảo mật danh tính:** Tuyệt đối không lưu số Căn cước công dân (CCCD).
7. **Bàn giao sảnh:** Ảnh Check-in / Check-out được server bóc EXIF, đóng dấu mã đơn + thời gian server, băm SHA-256 đối chiếu tranh chấp.
8. **Tự động huỷ đơn:** Đơn hàng quá 15 phút không được chủ duyệt sẽ tự động huỷ qua lazy-check hoặc cron container scheduler.

---

## 🧪 Chạy Kiểm thử (Unit Tests)

Chạy toàn bộ test suite bằng Docker:

```bash
docker compose exec web pytest -v
```

Hoặc qua Makefile:

```bash
make test
```

---

## 🛠️ Các Lệnh Thao tác Thường dùng

- Khởi động toàn bộ: `make up`
- Dừng hệ thống: `make down`
- Tái lập trình cơ sở dữ liệu: `make reset`
- Nạp lại dữ liệu mẫu: `make seed`
- Mở Django shell: `make shell`
- Xuất lại file schema: `make schema`
