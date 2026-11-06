from rest_framework import serializers

from apps.accounts.models import User


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, max_length=15)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True, max_length=15)
    otp_code = serializers.CharField(required=True, max_length=6)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "building",
            "unit_number",
            "is_resident_verified",
            "resident_proof",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "building", "unit_number"]


class ResidentProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["resident_proof"]

    def validate_resident_proof(self, value):
        if not value:
            raise serializers.ValidationError("Vui lòng tải lên minh chứng cư dân.")
        from django.conf import settings

        max_size = getattr(settings, "MAX_IMAGE_SIZE", 5 * 1024 * 1024)
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Kích thước ảnh tối đa là {max_size // (1024 * 1024)} MB."
            )
        return value
