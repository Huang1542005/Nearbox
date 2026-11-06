from django.db import models as db_models
from django.utils import timezone
from rest_framework import serializers

from apps.core.constants import LedgerKind
from .models import LedgerEntry, Wallet


class LedgerEntrySerializer(serializers.ModelSerializer):
    order = serializers.CharField(source="order.code", read_only=True)

    class Meta:
        model = LedgerEntry
        fields = ["id", "order", "kind", "amount", "description", "created_at"]
        read_only_fields = fields


class WalletSerializer(serializers.ModelSerializer):
    monthly_earnings = serializers.SerializerMethodField()
    ledger_history = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ["balance", "monthly_earnings", "ledger_history"]
        read_only_fields = fields

    def get_monthly_earnings(self, obj) -> int:
        """Tổng owner_payout trong tháng này."""
        now = timezone.now()
        return (
            LedgerEntry.objects.filter(
                kind=LedgerKind.OWNER_PAYOUT,
                order__owner=obj.user,
                created_at__year=now.year,
                created_at__month=now.month,
            ).aggregate(total=db_models.Sum("amount"))["total"]
            or 0
        )

    def get_ledger_history(self, obj):
        """50 bút toán gần nhất liên quan đến user."""
        entries = (
            LedgerEntry.objects.filter(
                db_models.Q(order__owner=obj.user)
                | db_models.Q(order__renter=obj.user)
            )
            .select_related("order")
            .order_by("-created_at")[:50]
        )
        return LedgerEntrySerializer(entries, many=True).data
