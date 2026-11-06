import hashlib
import io
from datetime import timedelta

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.core.constants import OrderStatus
from apps.core.exceptions import BusinessError
from apps.orders import services
from apps.orders.models import Order, HandoverPhoto
from apps.orders.serializers import (
    ConfirmHandoverSerializer,
    OrderActionSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    PhotoUploadSerializer,
)


# ── Photo Processing Utility ─────────────────────────────────────────

def process_handover_photo(image_file, order_code: str) -> tuple:
    """
    Process an uploaded handover photo:
    1. Compute SHA-256 hash of original bytes
    2. Strip EXIF by re-creating from pixel data
    3. Stamp order code + timestamp on the image
    4. Return (processed_file, sha256_hex, taken_at)
    """
    raw_bytes = image_file.read()
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    taken_at = timezone.now()

    # Open image and strip EXIF by copying pixel data
    original = Image.open(io.BytesIO(raw_bytes))
    clean = Image.new(original.mode, original.size)
    clean.putdata(list(original.getdata()))

    # Convert to RGB if necessary (e.g. RGBA PNGs)
    if clean.mode not in ("RGB", "L"):
        clean = clean.convert("RGB")

    # Stamp text onto image
    draw = ImageDraw.Draw(clean)
    stamp_text = f"{order_code} | {taken_at.strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        font = ImageFont.truetype("arial.ttf", size=max(16, clean.width // 40))
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Position at bottom-left with a small margin
    margin = 10
    text_bbox = draw.textbbox((0, 0), stamp_text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    x = margin
    y = clean.height - text_h - margin

    # Draw shadow for readability
    draw.text((x + 1, y + 1), stamp_text, fill="black", font=font)
    draw.text((x, y), stamp_text, fill="white", font=font)

    # Save to buffer
    buf = io.BytesIO()
    clean.save(buf, format="JPEG", quality=90)
    buf.seek(0)

    processed_file = InMemoryUploadedFile(
        file=buf,
        field_name="image",
        name=image_file.name,
        content_type="image/jpeg",
        size=buf.getbuffer().nbytes,
        charset=None,
    )
    return processed_file, sha256_hex, taken_at


# ── Lazy Expire Check ────────────────────────────────────────────────

def lazy_expire_check(order: Order) -> None:
    """Auto-cancel an order if its deadline has passed."""
    if (
        order.status == OrderStatus.PENDING_OWNER
        and order.deadline_at
        and order.deadline_at < timezone.now()
    ):
        try:
            services.expire_overdue(order)
        except BusinessError:
            pass  # already transitioned


# ── ViewSet ───────────────────────────────────────────────────────────

class OrderViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["status"]

    def get_queryset(self):
        user = self.request.user
        return (
            Order.objects
            .filter(Q(renter=user) | Q(owner=user))
            .select_related("item", "renter", "owner")
            .prefetch_related("events", "photos")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        return OrderListSerializer

    # ── List ──────────────────────────────────────────────────────────

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # ── Retrieve ──────────────────────────────────────────────────────

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        lazy_expire_check(instance)
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ── Create ────────────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        item = data["_item"]
        breakdown = data["_breakdown"]
        timeout_minutes = getattr(settings, "ORDER_PENDING_TIMEOUT_MINUTES", 15)

        order = Order.objects.create(
            item=item,
            renter=request.user,
            owner=item.owner,
            status=OrderStatus.PENDING_OWNER,
            rental_duration=data["rental_duration"],
            pickup_slot=data["pickup_slot"],
            pickup_time=data["pickup_time"],
            daily_price=item.daily_price,
            rental_fee=breakdown["rental_fee"],
            deposit=breakdown["deposit"],
            platform_fee=breakdown["platform_fee"],
            total_amount=breakdown["total_renter_pays"],
            commission=breakdown["commission"],
            owner_payout=breakdown["owner_payout"],
            risk_fund=breakdown["risk_fund"],
            deadline_at=timezone.now() + timedelta(minutes=timeout_minutes),
        )

        out = OrderDetailSerializer(order, context={"request": request})
        return Response(out.data, status=http_status.HTTP_201_CREATED)

    # ── Owner actions ─────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        order = self.get_object()
        lazy_expire_check(order)
        if order.owner_id != request.user.id:
            return Response(
                {"error": True, "message": "Chỉ chủ sản phẩm mới có thể duyệt."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.approve_order(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        order = self.get_object()
        lazy_expire_check(order)
        if order.owner_id != request.user.id:
            return Response(
                {"error": True, "message": "Chỉ chủ sản phẩm mới có thể từ chối."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.reject_order(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    # ── Renter actions ────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="confirm-payment-sent")
    def confirm_payment_sent(self, request, pk=None):
        order = self.get_object()
        lazy_expire_check(order)
        if order.renter_id != request.user.id:
            return Response(
                {"error": True, "message": "Chỉ người thuê mới có thể xác nhận thanh toán."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.confirm_payment_sent(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="confirm-handover")
    def confirm_handover(self, request, pk=None):
        order = self.get_object()
        lazy_expire_check(order)
        if order.renter_id != request.user.id:
            return Response(
                {"error": True, "message": "Chỉ người thuê mới có thể xác nhận nhận hàng."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = ConfirmHandoverSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.confirm_handover(
                order,
                request.user,
                liability_waiver_consent=ser.validated_data.get("liability_waiver_consent", True),
            )
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    # ── Shared actions ────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="cancel-at-lobby")
    def cancel_at_lobby(self, request, pk=None):
        order = self.get_object()
        if order.renter_id != request.user.id and order.owner_id != request.user.id:
            return Response(
                {"error": True, "message": "Bạn không có quyền huỷ đơn này."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.cancel_at_lobby(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="return")
    def return_item(self, request, pk=None):
        order = self.get_object()
        if order.renter_id != request.user.id:
            return Response(
                {"error": True, "message": "Chỉ người thuê mới có thể trả hàng."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.return_item(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="confirm-return")
    def confirm_return(self, request, pk=None):
        order = self.get_object()
        if order.owner_id != request.user.id:
            return Response(
                {"error": True, "message": "Chỉ chủ sản phẩm mới có thể xác nhận trả hàng."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.confirm_return(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="open-dispute")
    def open_dispute(self, request, pk=None):
        order = self.get_object()
        if order.renter_id != request.user.id and order.owner_id != request.user.id:
            return Response(
                {"error": True, "message": "Bạn không có quyền mở tranh chấp."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        ser = OrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.open_dispute(order, request.user, note=ser.validated_data.get("note", ""))
        except BusinessError as e:
            return e.to_response()
        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    # ── Photo upload ──────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="photos")
    def photos(self, request, pk=None):
        order = self.get_object()
        ser = PhotoUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        processed_file, sha256_hex, taken_at = process_handover_photo(
            ser.validated_data["image"], order.code,
        )

        photo = HandoverPhoto.objects.create(
            order=order,
            photo_type=ser.validated_data["photo_type"],
            image=processed_file,
            taken_at=taken_at,
            uploaded_by=request.user,
            sha256=sha256_hex,
        )

        from apps.orders.serializers import HandoverPhotoSerializer as HPS
        return Response(
            HPS(photo, context={"request": request}).data,
            status=http_status.HTTP_201_CREATED,
        )
