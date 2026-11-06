from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps.core.constants import BUILDINGS


BUILDING_CHOICES = [(b, b) for b in BUILDINGS]


class UserManager(BaseUserManager):
    """Custom manager — creates users by phone (no password required for OTP auth)."""

    def create_user(self, phone, **extra_fields):
        if not phone:
            raise ValueError("Số điện thoại là bắt buộc.")
        user = self.model(phone=phone, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser phải có is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser phải có is_superuser=True.")

        return self.create_user(phone, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField("Số điện thoại", max_length=15, unique=True)
    full_name = models.CharField("Họ và tên", max_length=150, blank=True, default="")
    building = models.CharField(
        "Toà nhà",
        max_length=10,
        choices=BUILDING_CHOICES,
        blank=True,
        default="",
    )
    unit_number = models.CharField("Số căn hộ", max_length=20, blank=True, default="")
    is_resident_verified = models.BooleanField("Đã xác minh cư dân", default=False)
    resident_proof = models.ImageField(
        "Minh chứng cư dân",
        upload_to="resident_proofs/",
        blank=True,
        null=True,
    )

    is_active = models.BooleanField("Đang hoạt động", default=True)
    is_staff = models.BooleanField("Nhân viên", default=False)

    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name or self.phone
