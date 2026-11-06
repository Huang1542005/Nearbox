import csv
from datetime import timedelta

from django.db import models as db_models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.catalog.models import Item
from apps.core.constants import ItemStatus, LedgerKind, OrderStatus
from apps.core.exceptions import BusinessError
from apps.escrow.models import LedgerEntry
from apps.orders import services
from apps.orders.models import HandoverPhoto, Order, OrderEvent
from .models import Dispute
from .serializers import (
    DisputeDetailSerializer,
    DisputeListSerializer,
    DisputeResolveSerializer,
    PendingItemReviewSerializer,
    ResidentReviewSerializer,
)


class DashboardView(APIView):
    """GET /api/v1/admin/dashboard/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())

        # 1. Total escrow currently held
        active_escrow_orders = Order.objects.filter(
            status__in=[
                OrderStatus.ESCROW_HELD,
                OrderStatus.HANDED_OVER,
                OrderStatus.RETURNED,
                OrderStatus.DISPUTED,
            ]
        )
        total_escrow_held = (
            active_escrow_orders.aggregate(
                total=db_models.Sum("total_amount")
            )["total"]
            or 0
        )

        # 2. Orders today
        orders_today = Order.objects.filter(created_at__gte=today_start).count()

        # 3. Open disputes
        open_disputes = Dispute.objects.filter(status=Dispute.STATUS_OPEN).count()

        # 4. Valid listings this week
        valid_listings_this_week = Item.objects.filter(
            status=ItemStatus.ACTIVE,
            created_at__gte=week_start,
        ).count()

        # 5. Average handover time (minutes)
        # Difference between 'escrow_held' OrderEvent and 'handed_over' OrderEvent
        completed_or_handed = Order.objects.filter(
            status__in=[
                OrderStatus.HANDED_OVER,
                OrderStatus.RETURNED,
                OrderStatus.COMPLETED,
            ]
        )
        total_diff_minutes = 0.0
        diff_count = 0
        for ord_obj in completed_or_handed:
            held_event = ord_obj.events.filter(to_status=OrderStatus.ESCROW_HELD).first()
            handed_event = ord_obj.events.filter(to_status=OrderStatus.HANDED_OVER).first()
            if held_event and handed_event and handed_event.created_at >= held_event.created_at:
                diff = (handed_event.created_at - held_event.created_at).total_seconds() / 60.0
                total_diff_minutes += diff
                diff_count += 1

        avg_handover_time = round(total_diff_minutes / diff_count, 1) if diff_count > 0 else 0.0

        # 6. Deposit refund rate without complaints
        # Completed orders without dispute vs all completed orders
        completed_orders = Order.objects.filter(status=OrderStatus.COMPLETED)
        completed_count = completed_orders.count()
        if completed_count > 0:
            undisputed_count = completed_orders.filter(disputes__isnull=True).count()
            deposit_refund_rate = round((undisputed_count / completed_count) * 100, 1)
        else:
            deposit_refund_rate = 100.0

        return Response({
            "total_escrow_held": total_escrow_held,
            "orders_today": orders_today,
            "open_disputes": open_disputes,
            "avg_handover_time_minutes": avg_handover_time,
            "deposit_refund_rate": deposit_refund_rate,
            "valid_listings_this_week": valid_listings_this_week,
        })


class ResidentListView(APIView):
    """GET /api/v1/admin/residents/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get("status")
        users = User.objects.all().order_by("-date_joined")
        if status_filter == "pending":
            users = users.filter(is_resident_verified=False, resident_proof__isnull=False).exclude(resident_proof="")
        elif status_filter == "verified":
            users = users.filter(is_resident_verified=True)
        serializer = ResidentReviewSerializer(users, many=True, context={"request": request})
        return Response(serializer.data)


class ResidentApproveView(APIView):
    """POST /api/v1/admin/residents/{id}/approve/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_resident_verified = True
        user.save(update_fields=["is_resident_verified"])
        return Response({
            "success": True,
            "message": f"Đã duyệt xác minh cư dân cho {user.phone}.",
            "user": ResidentReviewSerializer(user, context={"request": request}).data,
        })


class ResidentRejectView(APIView):
    """POST /api/v1/admin/residents/{id}/reject/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_resident_verified = False
        user.save(update_fields=["is_resident_verified"])
        return Response({
            "success": True,
            "message": f"Đã từ chối xác minh cư dân cho {user.phone}.",
            "user": ResidentReviewSerializer(user, context={"request": request}).data,
        })


class PendingItemListView(APIView):
    """GET /api/v1/admin/items/pending/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        items = Item.objects.filter(status=ItemStatus.PENDING_REVIEW).order_by("-created_at")
        serializer = PendingItemReviewSerializer(items, many=True, context={"request": request})
        return Response(serializer.data)


class PendingItemApproveView(APIView):
    """POST /api/v1/admin/items/pending/{id}/approve/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk)
        item.status = ItemStatus.ACTIVE
        item.save(update_fields=["status", "updated_at"])
        return Response({
            "success": True,
            "message": f"Đã duyệt sản phẩm '{item.name}'.",
        })


class PendingItemRejectView(APIView):
    """POST /api/v1/admin/items/pending/{id}/reject/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk)
        item.status = ItemStatus.REJECTED
        item.save(update_fields=["status", "updated_at"])
        return Response({
            "success": True,
            "message": f"Đã từ chối sản phẩm '{item.name}'.",
        })


class AdminConfirmPaymentView(APIView):
    """POST /api/v1/admin/orders/{id}/confirm-payment/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            services.admin_confirm_payment(order, request.user)
        except BusinessError as e:
            return e.to_response()

        from apps.orders.serializers import OrderDetailSerializer
        order.refresh_from_db()
        return Response({
            "success": True,
            "message": "Đã xác nhận thanh toán thành công.",
            "order": OrderDetailSerializer(order, context={"request": request}).data,
        })


class DisputeListView(APIView):
    """GET /api/v1/admin/disputes/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_param = request.query_params.get("status")
        disputes = Dispute.objects.all().select_related("order", "opened_by", "decided_by")
        if status_param:
            disputes = disputes.filter(status=status_param)
        serializer = DisputeListSerializer(disputes, many=True, context={"request": request})
        return Response(serializer.data)


class DisputeDetailView(APIView):
    """GET /api/v1/admin/disputes/{id}/"""
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        dispute = get_object_or_404(
            Dispute.objects.select_related("order", "opened_by", "decided_by"),
            pk=pk,
        )
        serializer = DisputeDetailSerializer(dispute, context={"request": request})
        return Response(serializer.data)


class DisputeResolveView(APIView):
    """POST /api/v1/admin/disputes/{id}/resolve/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        dispute = get_object_or_404(Dispute.objects.select_related("order"), pk=pk)
        serializer = DisputeResolveSerializer(data=request.data, context={"dispute": dispute})
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            services.resolve_dispute(
                dispute=dispute,
                decision=data["decision"],
                deducted_amount=data.get("deducted_amount", 0),
                admin_user=request.user,
                note=data.get("note", ""),
            )
        except BusinessError as e:
            return e.to_response()

        dispute.refresh_from_db()
        return Response({
            "success": True,
            "message": "Đã xử lý tranh chấp thành công.",
            "dispute": DisputeDetailSerializer(dispute, context={"request": request}).data,
        })


class ExportOrdersCSVView(APIView):
    """GET /api/v1/admin/export/orders.csv"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="orders.csv"'
        response.write("\ufeff")  # BOM for Excel UTF-8 support

        writer = csv.writer(response)
        writer.writerow([
            "Mã đơn", "Sản phẩm", "Người thuê", "Chủ sở hữu", "Trạng thái",
            "Thời hạn", "Khung giờ nhận", "Giá/ngày", "Phí thuê", "Tiền cọc",
            "Phí nền tảng", "Tổng thanh toán", "Hoa hồng", "Thanh toán chủ",
            "Quỹ rủi ro", "Hạn chót", "Ngày tạo",
        ])

        for order in Order.objects.all().select_related("item", "renter", "owner").order_by("-created_at"):
            writer.writerow([
                order.code,
                order.item.name,
                order.renter.phone,
                order.owner.phone,
                order.get_status_display(),
                order.get_rental_duration_display(),
                order.get_pickup_slot_display(),
                order.daily_price,
                order.rental_fee,
                order.deposit,
                order.platform_fee,
                order.total_amount,
                order.commission,
                order.owner_payout,
                order.risk_fund,
                order.deadline_at.strftime("%Y-%m-%d %H:%M:%S") if order.deadline_at else "",
                order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
        return response


class ExportEventsCSVView(APIView):
    """GET /api/v1/admin/export/events.csv"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="order_events.csv"'
        response.write("\ufeff")  # BOM for Excel UTF-8 support

        writer = csv.writer(response)
        writer.writerow([
            "ID", "Mã đơn", "Người thực hiện", "Từ trạng thái", "Sang trạng thái", "Ghi chú", "Thời gian",
        ])

        for event in OrderEvent.objects.all().select_related("order", "actor").order_by("created_at"):
            writer.writerow([
                event.id,
                event.order.code,
                event.actor.phone if event.actor else "Hệ thống",
                event.from_status,
                event.to_status,
                event.note,
                event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
        return response
