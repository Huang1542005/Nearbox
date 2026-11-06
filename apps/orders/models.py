import uuid

from django.conf import settings
from django.db import models

from apps.core.constants import (
    LOBBY_SLOTS,
    OrderStatus,
    RentalDuration,
    PLATFORM_FEE,
)


def generate_order_code() -> str:
    """Tạo mã đơn duy nhất dạng NBX-XXXXXX."""
    return f"NBX-{uuid.uuid4().hex[:6].upper()}"


class Order(models.Model):
    code = models.CharField(
        "Mã đơn", max_length=20, unique=True, default=generate_order_code, editable=False,
    )
    item = models.ForeignKey(
        "catalog.Item", on_delete=models.PROTECT, verbose_name="Sản phẩm",
        related_name="orders",
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        verbose_name="Người thuê", related_name="rented_orders",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        verbose_name="Chủ sở hữu", related_name="owned_orders",
    )
    status = models.CharField(
        "Trạng thái", max_length=30,
        choices=OrderStatus.CHOICES, default=OrderStatus.PENDING_OWNER,
    )
    rental_duration = models.CharField(
        "Thời hạn thuê", max_length=20, choices=RentalDuration.CHOICES,
    )
    pickup_slot = models.CharField(
        "Khung giờ nhận", max_length=20, choices=LOBBY_SLOTS,
    )
    pickup_time = models.DateTimeField("Thời gian nhận")

    # ── Pricing snapshot ──────────────────────────────────────────────
    daily_price = models.BigIntegerField("Giá thuê/ngày (VND)")
    rental_fee = models.BigIntegerField("Phí thuê (VND)")
    deposit = models.BigIntegerField("Tiền cọc (VND)")
    platform_fee = models.BigIntegerField("Phí nền tảng (VND)", default=PLATFORM_FEE)
    total_amount = models.BigIntegerField("Tổng thanh toán (VND)")
    commission = models.BigIntegerField("Hoa hồng NearBox (VND)")
    owner_payout = models.BigIntegerField("Thanh toán cho chủ (VND)")
    risk_fund = models.BigIntegerField("Quỹ rủi ro (VND)")

    # ── Lifecycle ─────────────────────────────────────────────────────
    deadline_at = models.DateTimeField("Hạn chót", null=True, blank=True)
    liability_waiver_accepted = models.BooleanField(
        "Đã chấp nhận miễn trừ trách nhiệm", default=False,
    )
    cancelled_reason = models.TextField("Lý do huỷ", blank=True, default="")

    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        verbose_name = "Đơn thuê"
        verbose_name_plural = "Đơn thuê"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    @property
    def qr_content(self) -> str:
        return f"NBX-{self.code}-{self.total_amount}"


class OrderEvent(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="events", verbose_name="Đơn thuê",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Người thực hiện",
    )
    from_status = models.CharField("Từ trạng thái", max_length=30, choices=OrderStatus.CHOICES)
    to_status = models.CharField("Sang trạng thái", max_length=30, choices=OrderStatus.CHOICES)
    note = models.TextField("Ghi chú", blank=True, default="")
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Sự kiện đơn"
        verbose_name_plural = "Sự kiện đơn"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.order.code}: {self.from_status} → {self.to_status}"


class HandoverPhoto(models.Model):
    PHOTO_TYPE_CHOICES = [
        ("checkin", "Check-in"),
        ("checkout", "Check-out"),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="photos", verbose_name="Đơn thuê",
    )
    photo_type = models.CharField("Loại ảnh", max_length=10, choices=PHOTO_TYPE_CHOICES)
    image = models.ImageField("Ảnh", upload_to="handover_photos/")
    taken_at = models.DateTimeField("Thời gian chụp")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Người tải lên",
    )
    sha256 = models.CharField("SHA-256", max_length=64)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Ảnh bàn giao"
        verbose_name_plural = "Ảnh bàn giao"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order.code} – {self.photo_type}"
