from django.contrib import admin, messages

from apps.core.constants import ItemStatus, MAX_RETAIL_PRICE
from .models import Category, Item, Quote, RentalRequest


# ── Category ──────────────────────────────────────────────────────────


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "group", "created_at")
    list_filter = ("group",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


# ── Item ──────────────────────────────────────────────────────────────


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "retail_price",
        "daily_price",
        "deposit_tier",
        "building",
        "status",
    )
    list_filter = ("status", "building", "category")
    search_fields = ("name", "owner__phone", "owner__full_name")
    readonly_fields = ("deposit_tier", "building", "created_at", "updated_at")
    actions = ["approve_item", "reject_item"]

    # ── Admin actions ─────────────────────────────────────────────────

    @admin.action(description="✅ Duyệt sản phẩm đã chọn")
    def approve_item(self, request, queryset):
        updated = queryset.filter(status=ItemStatus.PENDING_REVIEW).update(
            status=ItemStatus.ACTIVE,
        )
        self.message_user(
            request,
            f"Đã duyệt {updated} sản phẩm.",
            messages.SUCCESS,
        )

    @admin.action(description="❌ Từ chối sản phẩm đã chọn")
    def reject_item(self, request, queryset):
        updated = queryset.filter(status=ItemStatus.PENDING_REVIEW).update(
            status=ItemStatus.REJECTED,
        )
        self.message_user(
            request,
            f"Đã từ chối {updated} sản phẩm.",
            messages.SUCCESS,
        )

    # ── Change-form warnings ──────────────────────────────────────────

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            warnings = []
            if obj.retail_price > MAX_RETAIL_PRICE:
                warnings.append(
                    f"⚠️ Giá bán lẻ ({obj.retail_price:,} VND) vượt quá "
                    f"{MAX_RETAIL_PRICE:,} VND."
                )
            if obj.category and obj.category.slug == "electronics":
                warnings.append(
                    "⚠️ Danh mục điện tử hiện chưa được hỗ trợ cho thuê."
                )
            if warnings:
                for w in warnings:
                    self.message_user(request, w, messages.WARNING)
        return super().change_view(request, object_id, form_url, extra_context)


# ── Rental Request ────────────────────────────────────────────────────


@admin.register(RentalRequest)
class RentalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "category", "is_fulfilled", "created_at")
    list_filter = ("is_fulfilled", "category")
    search_fields = ("description", "requester__phone")


# ── Quote ─────────────────────────────────────────────────────────────


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("id", "rental_request", "item", "quoted_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("message", "quoted_by__phone")
