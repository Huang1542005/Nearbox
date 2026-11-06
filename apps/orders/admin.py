from django.contrib import admin, messages
from django.utils.html import format_html

from apps.core.exceptions import BusinessError
from apps.orders import services
from apps.orders.models import HandoverPhoto, Order, OrderEvent


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "from_status", "to_status", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


class HandoverPhotoInline(admin.TabularInline):
    model = HandoverPhoto
    extra = 0
    can_delete = False
    readonly_fields = ("photo_type", "image_preview", "taken_at", "uploaded_by", "sha256", "created_at")

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 80px; border-radius: 4px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Ảnh"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "item",
        "renter",
        "owner",
        "status",
        "rental_fee_display",
        "deposit_display",
        "total_amount_display",
        "deadline_at",
        "created_at",
    )
    list_filter = ("status", "rental_duration", "pickup_slot", "created_at")
    search_fields = ("code", "renter__phone", "owner__phone", "item__name")
    readonly_fields = (
        "code",
        "item",
        "renter",
        "owner",
        "daily_price",
        "rental_fee",
        "deposit",
        "platform_fee",
        "total_amount",
        "commission",
        "owner_payout",
        "risk_fund",
        "deadline_at",
        "qr_display",
        "liability_waiver_accepted",
        "cancelled_reason",
        "created_at",
        "updated_at",
    )
    inlines = [OrderEventInline, HandoverPhotoInline]
    actions = ["action_confirm_payment", "action_expire_overdue"]

    def rental_fee_display(self, obj):
        return f"{obj.rental_fee:,} đ"
    rental_fee_display.short_description = "Phí thuê"

    def deposit_display(self, obj):
        return f"{obj.deposit:,} đ"
    deposit_display.short_description = "Tiền cọc"

    def total_amount_display(self, obj):
        return f"{obj.total_amount:,} đ"
    total_amount_display.short_description = "Tổng tiền"

    def qr_display(self, obj):
        return obj.qr_content
    qr_display.short_description = "Nội dung QR chuyển khoản"

    @admin.action(description="Xác nhận đã nhận chuyển khoản (Chuyển sang Đã giữ cọc)")
    def action_confirm_payment(self, request, queryset):
        success_count = 0
        for order in queryset:
            try:
                services.admin_confirm_payment(order, request.user)
                success_count += 1
            except BusinessError as e:
                self.message_user(
                    request,
                    f"Đơn {order.code}: {e.message}",
                    level=messages.ERROR,
                )
        if success_count > 0:
            self.message_user(
                request,
                f"Đã xác nhận thanh toán thành công cho {success_count} đơn hàng.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Kiểm tra và tự huỷ nếu quá hạn 15 phút")
    def action_expire_overdue(self, request, queryset):
        for order in queryset:
            services.expire_overdue(order)
        self.message_user(request, "Đã cập nhật kiểm tra đơn quá hạn.", level=messages.INFO)


@admin.register(OrderEvent)
class OrderEventAdmin(admin.ModelAdmin):
    list_display = ("order", "actor", "from_status", "to_status", "created_at")
    list_filter = ("from_status", "to_status", "created_at")
    search_fields = ("order__code", "actor__phone", "note")
    readonly_fields = ("order", "actor", "from_status", "to_status", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HandoverPhoto)
class HandoverPhotoAdmin(admin.ModelAdmin):
    list_display = ("order", "photo_type", "image_preview", "taken_at", "uploaded_by", "sha256")
    list_filter = ("photo_type", "taken_at")
    search_fields = ("order__code", "uploaded_by__phone", "sha256")
    readonly_fields = ("order", "photo_type", "image_preview", "image", "taken_at", "uploaded_by", "sha256", "created_at")

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 120px; border-radius: 4px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Ảnh xem trước"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
