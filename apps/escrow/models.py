from django.conf import settings
from django.db import models

from apps.core.constants import LedgerKind


class LedgerEntry(models.Model):
    """
    Bút toán sổ cái — chỉ thêm, không sửa, không xoá.
    amount > 0  → tiền vào (hold / fee)
    amount < 0  → tiền ra  (release / payout)
    """

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        verbose_name="Đơn thuê",
    )
    kind = models.CharField(
        "Loại bút toán",
        max_length=30,
        choices=LedgerKind.CHOICES,
    )
    amount = models.BigIntegerField("Số tiền (VND)")
    balance_after = models.BigIntegerField(
        "Số dư sau giao dịch (VND)",
        null=True,
        blank=True,
    )
    description = models.TextField("Mô tả", blank=True, default="")
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Bút toán"
        verbose_name_plural = "Bút toán"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.order} | {self.get_kind_display()} | {self.amount:+,} VND"

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValueError("Bút toán sổ cái không thể chỉnh sửa.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Bút toán sổ cái không thể xoá.")


class Wallet(models.Model):
    """Ví người dùng — số dư được cache, có thể tính lại từ sổ cái."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
        verbose_name="Người dùng",
    )
    balance = models.BigIntegerField("Số dư (VND)", default=0)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        verbose_name = "Ví"
        verbose_name_plural = "Ví"

    def __str__(self):
        return f"Ví {self.user} — {self.balance:,} VND"

    def recalculate(self):
        """Tính lại số dư từ tất cả bút toán liên quan đến user."""
        total = (
            LedgerEntry.objects.filter(
                models.Q(order__owner=self.user) | models.Q(order__renter=self.user)
            ).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )
        self.balance = total
        self.save(update_fields=["balance", "updated_at"])
