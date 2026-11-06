from django.conf import settings
from django.db import models

from apps.core.constants import CATEGORY_GROUPS, ItemStatus


class Category(models.Model):
    """Danh mục sản phẩm cho thuê."""

    name = models.CharField("Tên danh mục", max_length=100)
    slug = models.SlugField("Slug", max_length=120, unique=True)
    group = models.CharField(
        "Nhóm danh mục",
        max_length=50,
        choices=CATEGORY_GROUPS,
    )
    description = models.TextField("Mô tả", blank=True, default="")
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Danh mục"
        verbose_name_plural = "Danh mục"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    """Sản phẩm cho thuê được đăng bởi cư dân."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Chủ sở hữu",
    )
    name = models.CharField("Tên sản phẩm", max_length=200)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name="Danh mục",
    )
    description = models.TextField("Mô tả", blank=True, default="")
    photo_1 = models.ImageField("Ảnh chính", upload_to="items/")
    photo_2 = models.ImageField(
        "Ảnh phụ",
        upload_to="items/",
        blank=True,
        null=True,
    )
    retail_price = models.BigIntegerField("Giá bán lẻ (VND)")
    daily_price = models.BigIntegerField("Giá thuê / ngày (VND)")
    deposit_tier = models.BigIntegerField("Tiền cọc (VND)")
    building = models.CharField("Toà nhà", max_length=10)
    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=ItemStatus.CHOICES,
        default=ItemStatus.PENDING_REVIEW,
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        verbose_name = "Sản phẩm"
        verbose_name_plural = "Sản phẩm"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def savings_percent(self) -> int:
        """Tính % tiết kiệm khi thuê so với mua mới."""
        if not self.retail_price:
            return 0
        return round((1 - self.daily_price / self.retail_price) * 100)

    @property
    def deposit(self) -> int:
        return self.deposit_tier


class RentalRequest(models.Model):
    """Yêu cầu thuê đồ — cư dân đăng nhu cầu để nhận báo giá."""

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rental_requests",
        verbose_name="Người yêu cầu",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="rental_requests",
        verbose_name="Danh mục",
    )
    description = models.TextField("Mô tả nhu cầu")
    budget_max = models.BigIntegerField(
        "Ngân sách tối đa (VND)",
        blank=True,
        null=True,
    )
    is_fulfilled = models.BooleanField("Đã hoàn thành", default=False)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Yêu cầu thuê"
        verbose_name_plural = "Yêu cầu thuê"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Yêu cầu #{self.pk} — {self.requester}"


class Quote(models.Model):
    """Báo giá cho một yêu cầu thuê."""

    rental_request = models.ForeignKey(
        RentalRequest,
        on_delete=models.CASCADE,
        related_name="quotes",
        verbose_name="Yêu cầu thuê",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="quotes",
        verbose_name="Sản phẩm",
    )
    quoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quotes",
        verbose_name="Người báo giá",
    )
    message = models.TextField("Lời nhắn", blank=True, default="")
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Báo giá"
        verbose_name_plural = "Báo giá"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Báo giá #{self.pk} cho yêu cầu #{self.rental_request_id}"
