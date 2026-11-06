from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import User
from apps.catalog.models import Item
from apps.core.constants import DisputeDecision
from apps.orders.models import HandoverPhoto, Order
from .models import Dispute, DisputeLog


class DisputeLogSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = DisputeLog
        fields = ["id", "actor", "action", "note", "created_at"]
        read_only_fields = fields


class HandoverPhotoDetailSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    uploaded_by = serializers.StringRelatedField()

    class Meta:
        model = HandoverPhoto
        fields = ["id", "photo_type", "image_url", "taken_at", "uploaded_by", "sha256", "created_at"]

    def get_image_url(self, obj) -> str:
        request = self.context.get("request")
        if request and obj.image:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            return f"{settings.PUBLIC_BASE_URL}{obj.image.url}"
        return ""


class DisputeListSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(source="order.code", read_only=True)
    opened_by_phone = serializers.CharField(source="opened_by.phone", read_only=True)
    opened_by_name = serializers.CharField(source="opened_by.full_name", read_only=True)

    class Meta:
        model = Dispute
        fields = [
            "id",
            "order",
            "order_code",
            "opened_by",
            "opened_by_phone",
            "opened_by_name",
            "reason",
            "status",
            "decision",
            "deducted_amount",
            "decided_by",
            "decided_at",
            "created_at",
        ]
        read_only_fields = fields


class DisputeDetailSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(source="order.code", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    renter_phone = serializers.CharField(source="order.renter.phone", read_only=True)
    owner_phone = serializers.CharField(source="order.owner.phone", read_only=True)
    item_name = serializers.CharField(source="order.item.name", read_only=True)
    deposit = serializers.IntegerField(source="order.deposit", read_only=True)
    total_amount = serializers.IntegerField(source="order.total_amount", read_only=True)
    logs = DisputeLogSerializer(many=True, read_only=True)
    checkin_photos = serializers.SerializerMethodField()
    checkout_photos = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            "id",
            "order",
            "order_code",
            "order_status",
            "renter_phone",
            "owner_phone",
            "item_name",
            "deposit",
            "total_amount",
            "opened_by",
            "reason",
            "status",
            "decision",
            "deducted_amount",
            "decided_by",
            "decided_at",
            "created_at",
            "logs",
            "checkin_photos",
            "checkout_photos",
        ]
        read_only_fields = fields

    def get_checkin_photos(self, obj):
        photos = obj.order.photos.filter(photo_type="checkin")
        return HandoverPhotoDetailSerializer(photos, many=True, context=self.context).data

    def get_checkout_photos(self, obj):
        photos = obj.order.photos.filter(photo_type="checkout")
        return HandoverPhotoDetailSerializer(photos, many=True, context=self.context).data


class DisputeResolveSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=DisputeDecision.CHOICES)
    deducted_amount = serializers.IntegerField(required=False, default=0, min_value=0)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        decision = attrs.get("decision")
        deducted_amount = attrs.get("deducted_amount", 0)
        dispute = self.context.get("dispute")
        deposit = dispute.order.deposit if dispute else 0

        if decision == DisputeDecision.PARTIAL_DEDUCTION:
            if deducted_amount <= 0:
                raise serializers.ValidationError(
                    {"deducted_amount": "Với quyết định khấu trừ một phần, số tiền phải lớn hơn 0."}
                )
            if deducted_amount >= deposit:
                raise serializers.ValidationError(
                    {"deducted_amount": f"Số tiền khấu trừ một phần phải nhỏ hơn tiền cọc ({deposit:,} VND)."}
                )
        elif decision == DisputeDecision.FULL_DEDUCTION:
            attrs["deducted_amount"] = deposit
        elif decision == DisputeDecision.FULL_REFUND:
            attrs["deducted_amount"] = 0

        return attrs


class ResidentReviewSerializer(serializers.ModelSerializer):
    resident_proof_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "building",
            "unit_number",
            "is_resident_verified",
            "resident_proof_url",
            "date_joined",
        ]
        read_only_fields = fields

    def get_resident_proof_url(self, obj) -> str:
        request = self.context.get("request")
        if request and obj.resident_proof:
            return request.build_absolute_uri(obj.resident_proof.url)
        if obj.resident_proof:
            return f"{settings.PUBLIC_BASE_URL}{obj.resident_proof.url}"
        return ""


class PendingItemReviewSerializer(serializers.ModelSerializer):
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    photo_1_url = serializers.SerializerMethodField()
    photo_2_url = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "owner",
            "owner_phone",
            "retail_price",
            "daily_price",
            "deposit",
            "building",
            "description",
            "status",
            "photo_1_url",
            "photo_2_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_photo_1_url(self, obj) -> str:
        request = self.context.get("request")
        if request and obj.photo_1:
            return request.build_absolute_uri(obj.photo_1.url)
        if obj.photo_1:
            return f"{settings.PUBLIC_BASE_URL}{obj.photo_1.url}"
        return ""

    def get_photo_2_url(self, obj) -> str:
        request = self.context.get("request")
        if request and obj.photo_2:
            return request.build_absolute_uri(obj.photo_2.url)
        if obj.photo_2:
            return f"{settings.PUBLIC_BASE_URL}{obj.photo_2.url}"
        return ""
