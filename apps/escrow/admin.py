from django.contrib import admin

from .models import LedgerEntry, Wallet


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """Bút toán sổ cái — chỉ đọc, không cho sửa hay xoá."""

    list_display = ("order", "kind", "amount", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("order__code", "description")
    readonly_fields = (
        "order", "kind", "amount", "balance_after", "description", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__phone", "user__full_name")
    readonly_fields = ("user", "balance", "updated_at")
