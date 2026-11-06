from rest_framework import serializers
from django.conf import settings

from apps.core.constants import (
    RentalDuration,
    LOBBY_SLOTS,
    ErrorCode,
    ItemStatus,
)
from apps.core.utils import calculate_order_breakdown
from apps.orders.models import Order, OrderEvent, HandoverPhoto


# ── Nested helpers ────────────────────────────────────────────────────

class OrderEventSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = OrderEvent
        fields = ["actor", "from_status", "to_status", "note", "created_at"]
        read_only_fields = fields


class HandoverPhotoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    uploaded_by = serializers.StringRelatedField()

    class Meta:
        model = HandoverPhoto
        fields = ["id", "photo_type", "image", "taken_at", "uploaded_by", "sha256", "created_at"]
        read_only_fields = fields

    def get_image(self, obj) -> str:
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return f"{settings.PUBLIC_BASE_URL}{obj.image.url}"


# ── Item summary for order lists ──────────────────────────────────────

class _ItemBriefSerializer(serializers.Serializer):
    """Read-only item snapshot embedded in order serializers."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    photo_1 = serializers.ImageField()


# ── List / Detail ─────────────────────────────────────────────────────

class OrderListSerializer(serializers.ModelSerializer):
    item = _ItemBriefSerializer(read_only=True)
    renter = serializers.StringRelatedField()
    owner = serializers.StringRelatedField()
    qr_content = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "code", "item", "renter", "owner", "status",
            "rental_fee", "deposit", "platform_fee", "total_amount",
            "pickup_slot", "pickup_time", "deadline_at",
            "created_at", "qr_content",
        ]
        read_only_fields = fields


class OrderDetailSerializer(OrderListSerializer):
    events = OrderEventSerializer(many=True, read_only=True)
    photos = HandoverPhotoSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + [
            "rental_duration", "daily_price", "commission", "owner_payout",
            "risk_fund", "liability_waiver_accepted", "cancelled_reason",
            "events", "photos",
        ]
        read_only_fields = fields


# ── Create ────────────────────────────────────────────────────────────

class OrderCreateSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    rental_duration = serializers.ChoiceField(choices=RentalDuration.CHOICES)
    pickup_slot = serializers.ChoiceField(choices=LOBBY_SLOTS)
    pickup_time = serializers.DateTimeField()

    def validate_item(self, value):
        """Validate the item exists and is active."""
        from apps.catalog.models import Item

        try:
            item = Item.objects.select_related("owner").get(pk=value)
        except Item.DoesNotExist:
            raise serializers.ValidationError("Sản phẩm không tồn tại.")

        if item.status != ItemStatus.ACTIVE:
            raise serializers.ValidationError(
                "Sản phẩm không khả dụng.",
                code=ErrorCode.ITEM_NOT_AVAILABLE,
            )
        # Store the item object for later use
        self._item = item
        return value

    def validate(self, attrs):
        item = self._item
        user = self.context["request"].user

        if item.owner_id == user.id:
            raise serializers.ValidationError(
                {"item": "Bạn không thể thuê sản phẩm của chính mình."}
            )

        # Compute pricing breakdown
        duration_key = attrs["rental_duration"]
        multiplier = RentalDuration.MULTIPLIERS[duration_key]
        breakdown = calculate_order_breakdown(
            daily_price=item.daily_price,
            duration_multiplier=multiplier,
            deposit=item.deposit,
        )

        attrs["_item"] = item
        attrs["_breakdown"] = breakdown
        return attrs


# ── Action serializers ────────────────────────────────────────────────

class OrderActionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ConfirmHandoverSerializer(serializers.Serializer):
    liability_waiver_consent = serializers.BooleanField()

    def validate_liability_waiver_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "Bạn phải đồng ý miễn trừ trách nhiệm để tiếp tục.",
                code=ErrorCode.MISSING_WAIVER_CONSENT,
            )
        return value


class PhotoUploadSerializer(serializers.Serializer):
    photo_type = serializers.ChoiceField(choices=HandoverPhoto.PHOTO_TYPE_CHOICES)
    image = serializers.ImageField()

    def validate_image(self, value):
        max_size = getattr(settings, "MAX_IMAGE_SIZE", 5 * 1024 * 1024)
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Kích thước ảnh không được vượt quá {max_size // (1024 * 1024)}MB.",
                code=ErrorCode.IMAGE_TOO_LARGE,
            )
        return value
