import random
import logging

from django.conf import settings
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView  # noqa: F401 — re-export

from apps.accounts.models import User
from apps.accounts.serializers import (
    RequestOTPSerializer,
    ResidentProofSerializer,
    UserSerializer,
    UserUpdateSerializer,
    VerifyOTPSerializer,
)

logger = logging.getLogger(__name__)


# ── OTP helpers (mock) ────────────────────────────────────────────────
_otp_store: dict[str, str] = {}  # phone → otp (in-memory, dev only)


def _generate_otp(phone: str) -> str:
    code = f"{random.randint(0, 999999):06d}"
    _otp_store[phone] = code
    return code


def _verify_otp(phone: str, code: str) -> bool:
    if settings.DEBUG and code == "000000":
        return True
    return _otp_store.get(phone) == code


# ── Views ─────────────────────────────────────────────────────────────
class RequestOTPView(generics.GenericAPIView):
    """POST /auth/request-otp/ — Gửi mã OTP đến số điện thoại."""

    serializer_class = RequestOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        otp_code = _generate_otp(phone)
        # Mock: print to console instead of sending SMS
        logger.info("OTP cho %s: %s", phone, otp_code)
        print(f"[OTP] {phone}: {otp_code}")  # noqa: T201

        return Response(
            {"message": "Mã OTP đã được gửi"},
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(generics.GenericAPIView):
    """POST /auth/verify-otp/ — Xác thực OTP và trả về JWT tokens."""

    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        otp_code = serializer.validated_data["otp_code"]

        if not _verify_otp(phone, otp_code):
            return Response(
                {"detail": "Mã OTP không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create user
        user, _created = User.objects.get_or_create(phone=phone)
        if _created:
            user.set_unusable_password()
            user.save()

        # Clear used OTP
        _otp_store.pop(phone, None)

        # Issue JWT
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )


class UserMeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /me/ — Xem và cập nhật hồ sơ người dùng."""

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserSerializer


class ResidentProofView(generics.UpdateAPIView):
    """POST /me/resident-proof/ — Upload minh chứng cư dân."""

    serializer_class = ResidentProofSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["post"]

    def get_object(self):
        return self.request.user

    def post(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)
