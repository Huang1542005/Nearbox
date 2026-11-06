from rest_framework import serializers
from django.conf import settings

from apps.core.constants import ErrorCode
from apps.core.utils import (
    get_deposit_tier,
    is_listing_blocked,
    suggested_price_range,
)
from .models import Category, Item, Quote, RentalRequest


# ── Helpers ────────────────────────────────────────────────────────────


def _absolute_image_url(image_field) -> str | None:
    """Build an absolute URL for an ImageField using PUBLIC_BASE_URL."""
    if not image_field:
        return None
    return f"{settings.PUBLIC_BASE_URL}{image_field.url}"


# ── Category ──────────────────────────────────────────────────────────


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


# ── Nested owner representation ──────────────────────────────────────


class OwnerBriefSerializer(serializers.Serializer):
    """Read-only nested owner info included in item serializers."""

    phone = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    building = serializers.CharField(read_only=True)


class CategoryBriefSerializer(serializers.Serializer):
    """Read-only nested category info included in item serializers."""

    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)


# ── Item List ─────────────────────────────────────────────────────────


class ItemListSerializer(serializers.ModelSerializer):
    owner = OwnerBriefSerializer(read_only=True)
    category = CategoryBriefSerializer(read_only=True)
    photo_1 = serializers.SerializerMethodField()
    savings_percent = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            "id",
            "name",
            "owner",
            "category",
            "photo_1",
            "retail_price",
            "daily_price",
            "deposit_tier",
            "building",
            "status",
            "savings_percent",
            "created_at",
        ]

    def get_photo_1(self, obj: Item) -> str | None:
        return _absolute_image_url(obj.photo_1)

    def get_savings_percent(self, obj: Item) -> int:
        return obj.savings_percent()


# ── Item Detail ───────────────────────────────────────────────────────


class ItemDetailSerializer(ItemListSerializer):
    photo_2 = serializers.SerializerMethodField()

    class Meta(ItemListSerializer.Meta):
        fields = ItemListSerializer.Meta.fields + [
            "photo_2",
            "description",
        ]

    def get_photo_2(self, obj: Item) -> str | None:
        return _absolute_image_url(obj.photo_2)


# ── Item Create ───────────────────────────────────────────────────────


class ItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = [
            "name",
            "category",
            "description",
            "photo_1",
            "photo_2",
            "retail_price",
            "daily_price",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        # Owner must be verified
        if not user.is_resident_verified:
            raise serializers.ValidationError(
                {"owner": "Bạn cần xác minh cư dân trước khi đăng sản phẩm."},
                code=ErrorCode.OWNER_NOT_VERIFIED,
            )

        # Check listing block
        category_slug = None
        category = attrs.get("category")
        if category:
            category_slug = category.slug

        block = is_listing_blocked(attrs["retail_price"], category_slug)
        if block:
            raise serializers.ValidationError(
                {"detail": block["reason"]},
                code=block["code"],
            )

        # Auto-assign deposit tier
        deposit = get_deposit_tier(attrs["retail_price"])
        if deposit is None:
            raise serializers.ValidationError(
                {"retail_price": "Không thể xác định mức cọc cho giá trị này."},
            )
        attrs["deposit_tier"] = deposit

        # Set building from owner
        attrs["building"] = user.building
        return attrs

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


# ── Price Suggestion ──────────────────────────────────────────────────


class PriceSuggestionSerializer(serializers.Serializer):
    """Input: retail_price + optional category_slug → suggestion."""

    retail_price = serializers.IntegerField(min_value=1)
    category_slug = serializers.SlugField(required=False, allow_blank=True)

    def validate(self, attrs):
        retail = attrs["retail_price"]
        slug = attrs.get("category_slug") or None

        block = is_listing_blocked(retail, slug)
        suggestion = suggested_price_range(retail)
        deposit = get_deposit_tier(retail)

        attrs["result"] = {
            "suggested_price": suggestion,
            "deposit_tier": deposit,
            "block_warning": block,
        }
        return attrs


# ── Rental Request ────────────────────────────────────────────────────


class RentalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalRequest
        fields = [
            "id",
            "requester",
            "category",
            "description",
            "budget_max",
            "is_fulfilled",
            "created_at",
        ]
        read_only_fields = ["id", "requester", "is_fulfilled", "created_at"]

    def create(self, validated_data):
        validated_data["requester"] = self.context["request"].user
        return super().create(validated_data)


# ── Quote ─────────────────────────────────────────────────────────────


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quote
        fields = [
            "id",
            "rental_request",
            "item",
            "quoted_by",
            "message",
            "created_at",
        ]
        read_only_fields = ["id", "quoted_by", "created_at"]

    def create(self, validated_data):
        validated_data["quoted_by"] = self.context["request"].user
        return super().create(validated_data)
