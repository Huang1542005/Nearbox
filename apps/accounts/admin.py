from django.contrib import admin
from django.utils.html import format_html

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        "phone",
        "full_name",
        "building",
        "unit_number",
        "is_resident_verified",
        "is_active",
        "created_at",
    ]
    list_filter = ["building", "is_resident_verified", "is_active"]
    search_fields = ["phone", "full_name"]
    readonly_fields = [
        "phone",
        "created_at",
        "updated_at",
        "resident_proof_preview",
    ]
    ordering = ["-created_at"]
    actions = ["approve_resident", "reject_resident"]

    fieldsets = (
        ("Thông tin cơ bản", {
            "fields": ("phone", "full_name", "building", "unit_number"),
        }),
        ("Xác minh cư dân", {
            "fields": (
                "is_resident_verified",
                "resident_proof",
                "resident_proof_preview",
            ),
        }),
        ("Quyền hạn", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Thời gian", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def resident_proof_preview(self, obj):
        if obj.resident_proof:
            return format_html(
                '<img src="{}" style="max-height:300px; max-width:400px;" />',
                obj.resident_proof.url,
            )
        return "Chưa tải lên"

    resident_proof_preview.short_description = "Xem minh chứng"

    @admin.action(description="Duyệt cư dân (xác minh)")
    def approve_resident(self, request, queryset):
        updated = queryset.update(is_resident_verified=True)
        self.message_user(request, f"Đã duyệt {updated} cư dân.")

    @admin.action(description="Từ chối cư dân (huỷ xác minh)")
    def reject_resident(self, request, queryset):
        queryset.update(is_resident_verified=False, resident_proof=None)
        # Delete actual proof files for rejected users
        for user in queryset:
            if user.resident_proof:
                user.resident_proof.delete(save=False)
        self.message_user(request, f"Đã từ chối {queryset.count()} cư dân và xoá minh chứng.")
