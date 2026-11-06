from django.contrib import admin, messages
from django.utils.html import format_html

from apps.core.constants import DisputeDecision
from apps.core.exceptions import BusinessError
from apps.orders import services
from .models import Dispute, DisputeLog


class DisputeLogInline(admin.TabularInline):
    model = DisputeLog
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "action", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "opened_by",
        "status",
        "decision",
        "deducted_amount_display",
        "decided_by",
        "decided_at",
        "created_at",
    )
    list_filter = ("status", "decision", "created_at")
    search_fields = ("order__code", "opened_by__phone", "reason")
    readonly_fields = (
        "order",
        "opened_by",
        "reason",
        "status",
        "decision",
        "deducted_amount",
        "decided_by",
        "decided_at",
        "created_at",
        "updated_at",
        "photos_comparison_display",
    )
    inlines = [DisputeLogInline]
    actions = ["action_resolve_full_refund", "action_resolve_full_deduction"]

    def deducted_amount_display(self, obj):
        return f"{obj.deducted_amount:,} đ"
    deducted_amount_display.short_description = "Khấu trừ"

    def photos_comparison_display(self, obj):
        if not obj or not obj.order_id:
            return "Không có thông tin đơn hàng."

        checkin_photos = obj.order.photos.filter(photo_type="checkin")
        checkout_photos = obj.order.photos.filter(photo_type="checkout")

        def render_photo_card(photo, label):
            img_html = f'<img src="{photo.image.url}" style="max-width: 320px; max-height: 240px; border-radius: 6px; border: 1px solid #ccc;" />' if photo.image else "Không có file ảnh"
            return f"""
            <div style="flex: 1; min-width: 300px; padding: 12px; background: #f9f9f9; border-radius: 8px; border: 1px solid #e0e0e0;">
                <h4 style="margin-top: 0; color: #1a73e8;">{label}</h4>
                <div style="margin-bottom: 8px;">{img_html}</div>
                <p style="margin: 4px 0; font-size: 12px;"><strong>Thời gian:</strong> {photo.taken_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p style="margin: 4px 0; font-size: 12px;"><strong>Người chụp:</strong> {photo.uploaded_by.phone}</p>
                <p style="margin: 4px 0; font-size: 11px; font-family: monospace; word-break: break-all;"><strong>SHA-256:</strong> {photo.sha256}</p>
            </div>
            """

        checkin_html = "".join([render_photo_card(p, "Ảnh Check-in (Lúc nhận đồ)") for p in checkin_photos]) or "<p><em>Chưa có ảnh Check-in</em></p>"
        checkout_html = "".join([render_photo_card(p, "Ảnh Check-out (Lúc trả đồ)") for p in checkout_photos]) or "<p><em>Chưa có ảnh Check-out</em></p>"

        container_html = f"""
        <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-top: 10px;">
            <div style="flex: 1;">
                <h3 style="margin-bottom: 10px;">1. Ảnh đối chiếu Check-in</h3>
                {checkin_html}
            </div>
            <div style="flex: 1;">
                <h3 style="margin-bottom: 10px;">2. Ảnh đối chiếu Check-out</h3>
                {checkout_html}
            </div>
        </div>
        """
        return format_html(container_html)

    photos_comparison_display.short_description = "Đối chiếu ảnh Check-in / Check-out"

    @admin.action(description="Giải quyết: Hoàn cọc 100% cho người thuê")
    def action_resolve_full_refund(self, request, queryset):
        for dispute in queryset:
            if dispute.status != Dispute.STATUS_OPEN:
                self.message_user(request, f"Tranh chấp #{dispute.id} không ở trạng thái mở.", level=messages.WARNING)
                continue
            try:
                services.resolve_dispute(
                    dispute=dispute,
                    decision=DisputeDecision.FULL_REFUND,
                    deducted_amount=0,
                    admin_user=request.user,
                    note="Admin giải quyết qua Django Admin: Hoàn cọc 100%.",
                )
                self.message_user(request, f"Đã giải quyết tranh chấp #{dispute.id}: Hoàn cọc 100%.", level=messages.SUCCESS)
            except BusinessError as e:
                self.message_user(request, f"Lỗi tranh chấp #{dispute.id}: {e.message}", level=messages.ERROR)

    @admin.action(description="Giải quyết: Khấu trừ 100% cọc bồi thường cho chủ đồ")
    def action_resolve_full_deduction(self, request, queryset):
        for dispute in queryset:
            if dispute.status != Dispute.STATUS_OPEN:
                self.message_user(request, f"Tranh chấp #{dispute.id} không ở trạng thái mở.", level=messages.WARNING)
                continue
            try:
                services.resolve_dispute(
                    dispute=dispute,
                    decision=DisputeDecision.FULL_DEDUCTION,
                    deducted_amount=dispute.order.deposit,
                    admin_user=request.user,
                    note="Admin giải quyết qua Django Admin: Khấu trừ 100% cọc.",
                )
                self.message_user(request, f"Đã giải quyết tranh chấp #{dispute.id}: Khấu trừ 100% cọc.", level=messages.SUCCESS)
            except BusinessError as e:
                self.message_user(request, f"Lỗi tranh chấp #{dispute.id}: {e.message}", level=messages.ERROR)


@admin.register(DisputeLog)
class DisputeLogAdmin(admin.ModelAdmin):
    list_display = ("dispute", "actor", "action", "note", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("dispute__order__code", "actor__phone", "note")
    readonly_fields = ("dispute", "actor", "action", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
