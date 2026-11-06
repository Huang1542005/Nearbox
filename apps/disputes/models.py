from django.conf import settings
from django.db import models

from apps.core.constants import DisputeDecision


class Dispute(models.Model):
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Đang xử lý"),
        (STATUS_RESOLVED, "Đã giải quyết"),
        (STATUS_CANCELLED, "Đã huỷ"),
    ]

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="disputes",
        verbose_name="Đơn thuê",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_disputes",
        verbose_name="Người mở khiếu nại",
    )
    reason = models.TextField("Lý do khiếu nại")
    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    decision = models.CharField(
        "Quyết định",
        max_length=30,
        choices=DisputeDecision.CHOICES,
        null=True,
        blank=True,
    )
    deducted_amount = models.BigIntegerField("Số tiền khấu trừ (VND)", default=0)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_disputes",
        verbose_name="Người giải quyết",
    )
    decided_at = models.DateTimeField("Thời gian giải quyết", null=True, blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        verbose_name = "Tranh chấp"
        verbose_name_plural = "Tranh chấp"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Tranh chấp #{self.id} – Đơn {self.order.code}"


class DisputeLog(models.Model):
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Khiếu nại",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Người thực hiện",
    )
    action = models.CharField("Hành động", max_length=50)
    note = models.TextField("Ghi chú", blank=True, default="")
    created_at = models.DateTimeField("Thời gian", auto_now_add=True)

    class Meta:
        verbose_name = "Nhật ký tranh chấp"
        verbose_name_plural = "Nhật ký tranh chấp"
        ordering = ["created_at"]

    def __str__(self):
        return f"Log #{self.id} – {self.action} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
