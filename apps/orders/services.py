"""
NearBox Order Services — ALL business logic lives here.
Views and Django Admin only call these functions.
Each function runs in transaction.atomic() with select_for_update() on the order.
Invalid transitions return BusinessError (409 with Vietnamese message).
"""
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.core.constants import (
    OrderStatus, VALID_TRANSITIONS, ErrorCode, LedgerKind,
    PLATFORM_FEE, COMMISSION_RATE, OWNER_PAYOUT_RATE,
    DisputeDecision,
)
from apps.core.exceptions import BusinessError
from apps.core.utils import round_vnd


def _transition(order, new_status, actor, note=""):
    """Validate and perform a state transition. Must be called inside atomic()."""
    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise BusinessError(
            message=f"Không thể chuyển đơn hàng từ '{order.get_status_display()}' "
                    f"sang '{dict(OrderStatus.CHOICES).get(new_status, new_status)}'.",
            error_code=ErrorCode.ORDER_INVALID_STATE,
            status_code=409,
        )
    from apps.orders.models import OrderEvent
    old_status = order.status
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    OrderEvent.objects.create(
        order=order,
        actor=actor,
        from_status=old_status,
        to_status=new_status,
        note=note,
    )


def _create_ledger(order, kind, amount, description=""):
    """Create an append-only ledger entry."""
    from apps.escrow.models import LedgerEntry
    LedgerEntry.objects.create(
        order=order,
        kind=kind,
        amount=amount,
        description=description,
    )


def _set_deadline(order, minutes=None):
    """Set or clear the deadline for the current state."""
    if minutes:
        order.deadline_at = timezone.now() + timezone.timedelta(minutes=minutes)
    else:
        order.deadline_at = None
    order.save(update_fields=["deadline_at", "updated_at"])


# ── Order Actions ──────────────────────────────────────────────────────

def approve_order(order, actor, note=""):
    """Owner approves the order → awaiting_payment."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.owner:
            raise BusinessError("Chỉ chủ đồ mới có thể duyệt đơn.", ErrorCode.PERMISSION_DENIED, 403)
        _transition(order, OrderStatus.AWAITING_PAYMENT, actor, note or "Chủ đồ đã duyệt đơn.")
        _set_deadline(order, None)  # No auto-cancel for payment
    return order


def reject_order(order, actor, note=""):
    """Owner rejects the order → cancelled."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.owner:
            raise BusinessError("Chỉ chủ đồ mới có thể từ chối đơn.", ErrorCode.PERMISSION_DENIED, 403)
        order.cancelled_reason = note or "Chủ đồ từ chối."
        order.save(update_fields=["cancelled_reason", "updated_at"])
        _transition(order, OrderStatus.CANCELLED, actor, note or "Chủ đồ từ chối.")
        _set_deadline(order, None)
    return order


def confirm_payment_sent(order, actor):
    """Renter confirms they sent the bank transfer (status stays, just logs)."""
    # This is informational — actual confirmation is by admin
    if actor != order.renter:
        raise BusinessError("Chỉ người thuê mới có thể xác nhận thanh toán.", ErrorCode.PERMISSION_DENIED, 403)
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise BusinessError(
            "Đơn hàng không ở trạng thái chờ thanh toán.",
            ErrorCode.ORDER_INVALID_STATE, 409,
        )
    from apps.orders.models import OrderEvent
    OrderEvent.objects.create(
        order=order,
        actor=actor,
        from_status=order.status,
        to_status=order.status,
        note="Người thuê xác nhận đã chuyển khoản.",
    )
    return order


def admin_confirm_payment(order, actor):
    """Admin confirms the bank transfer → escrow_held. Creates ledger entries."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if not actor.is_staff:
            raise BusinessError("Chỉ admin mới có thể xác nhận thanh toán.", ErrorCode.PERMISSION_DENIED, 403)
        _transition(order, OrderStatus.ESCROW_HELD, actor, "Admin xác nhận đã nhận tiền.")

        # Create ledger entries for the payment
        _create_ledger(order, LedgerKind.RENT_HOLD, order.rental_fee, "Giữ tiền thuê")
        _create_ledger(order, LedgerKind.DEPOSIT_HOLD, order.deposit, "Giữ tiền cọc")
        _create_ledger(order, LedgerKind.PLATFORM_FEE, order.platform_fee, "Phí nền tảng")

        _set_deadline(order, None)
    return order


def confirm_handover(order, actor, liability_waiver_consent=False):
    """Renter confirms handover at lobby with Check-in photo → handed_over."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.renter:
            raise BusinessError("Chỉ người thuê mới có thể xác nhận nhận đồ.", ErrorCode.PERMISSION_DENIED, 403)
        if not liability_waiver_consent:
            raise BusinessError(
                "Bạn phải đồng ý với điều khoản miễn trừ trách nhiệm.",
                ErrorCode.MISSING_WAIVER_CONSENT, 422,
            )
        # Check that a Check-in photo exists
        if not order.photos.filter(photo_type="checkin").exists():
            raise BusinessError(
                "Cần có ảnh Check-in trước khi xác nhận giao đồ.",
                ErrorCode.MISSING_CHECKIN_PHOTO, 422,
            )
        _transition(order, OrderStatus.HANDED_OVER, actor, "Đã giao đồ tại sảnh.")
        order.liability_waiver_accepted = True
        order.save(update_fields=["liability_waiver_accepted", "updated_at"])

        # Owner receives rent only after renter confirms receipt
        _create_ledger(order, LedgerKind.OWNER_PAYOUT, -order.owner_payout, "Thanh toán chủ đồ")
        _create_ledger(order, LedgerKind.COMMISSION, -order.commission, "Hoa hồng NearBox")

        # Risk fund
        risk_fund_rate = getattr(settings, "RISK_FUND_RATE", 0.04)
        nearbox_revenue = order.commission + order.platform_fee
        risk_fund_amount = round_vnd(int(nearbox_revenue * risk_fund_rate))
        _create_ledger(order, LedgerKind.RISK_FUND, risk_fund_amount, "Quỹ rủi ro")

    return order


def cancel_at_lobby(order, actor, note=""):
    """Cancel at lobby → cancelled, 100% refund."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.renter and actor != order.owner:
            raise BusinessError("Chỉ người thuê hoặc chủ đồ mới có thể huỷ.", ErrorCode.PERMISSION_DENIED, 403)

        reason = note or "Huỷ tại sảnh."
        order.cancelled_reason = reason
        order.save(update_fields=["cancelled_reason", "updated_at"])
        _transition(order, OrderStatus.CANCELLED, actor, reason)

        # If payment was held, refund everything
        if order.ledger_entries.filter(kind=LedgerKind.RENT_HOLD).exists():
            _create_ledger(order, LedgerKind.DEPOSIT_RELEASE, -order.deposit, "Hoàn cọc 100% – huỷ tại sảnh")
            _create_ledger(order, LedgerKind.RENT_HOLD, -order.rental_fee, "Hoàn tiền thuê – huỷ tại sảnh")
            _create_ledger(order, LedgerKind.PLATFORM_FEE, -order.platform_fee, "Hoàn phí – huỷ tại sảnh")

        _set_deadline(order, None)
    return order


def submit_return(order, actor, note=""):
    """Renter submits return with Check-out photo → returned."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.renter:
            raise BusinessError("Chỉ người thuê mới có thể trả đồ.", ErrorCode.PERMISSION_DENIED, 403)
        # Check that a Check-out photo exists
        if not order.photos.filter(photo_type="checkout").exists():
            raise BusinessError(
                "Cần có ảnh Check-out trước khi trả đồ.",
                ErrorCode.MISSING_CHECKOUT_PHOTO, 422,
            )
        _transition(order, OrderStatus.RETURNED, actor, note or "Người thuê đã trả đồ.")
    return order


return_item = submit_return


def confirm_return(order, actor, note=""):
    """Owner confirms return → completed, deposit released, payout done."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.owner:
            raise BusinessError("Chỉ chủ đồ mới có thể xác nhận trả đồ.", ErrorCode.PERMISSION_DENIED, 403)
        # Must have a checkout photo
        if not order.photos.filter(photo_type="checkout").exists():
            raise BusinessError(
                "Cần có ảnh Check-out trước khi xác nhận trả đồ.",
                ErrorCode.MISSING_CHECKOUT_PHOTO, 422,
            )
        _transition(order, OrderStatus.COMPLETED, actor, note or "Chủ đồ xác nhận trả đồ. Hoàn tất.")

        # Release deposit
        _create_ledger(order, LedgerKind.DEPOSIT_RELEASE, -order.deposit, "Hoàn cọc 100%")

        _set_deadline(order, None)
    return order


def open_dispute(order, actor, reason="", note=""):
    """Open a dispute on the order."""
    from apps.disputes.models import Dispute, DisputeLog

    actual_reason = reason or note or "Tranh chấp đơn hàng"
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if actor != order.renter and actor != order.owner:
            raise BusinessError("Chỉ người thuê hoặc chủ đồ mới có thể mở tranh chấp.", ErrorCode.PERMISSION_DENIED, 403)
        if order.status not in (OrderStatus.HANDED_OVER, OrderStatus.RETURNED):
            raise BusinessError(
                "Chỉ có thể mở tranh chấp khi đơn đang ở trạng thái 'Đã giao' hoặc 'Đã trả'.",
                ErrorCode.ORDER_INVALID_STATE, 409,
            )
        _transition(order, OrderStatus.DISPUTED, actor, f"Mở tranh chấp: {actual_reason}")

        dispute = Dispute.objects.create(
            order=order,
            opened_by=actor,
            reason=actual_reason,
        )
        DisputeLog.objects.create(
            dispute=dispute,
            actor=actor,
            action="open",
            note=actual_reason,
        )
    return dispute


def resolve_dispute(dispute, decision, deducted_amount, admin_user, note=""):
    """Admin resolves a dispute. Handles deposit based on decision."""
    from apps.disputes.models import DisputeLog

    with transaction.atomic():
        order = dispute.order.__class__.objects.select_for_update().get(pk=dispute.order.pk)

        if not admin_user.is_staff:
            raise BusinessError("Chỉ admin mới có thể xử lý tranh chấp.", ErrorCode.PERMISSION_DENIED, 403)

        dispute.status = "resolved"
        dispute.decision = decision
        dispute.decided_by = admin_user
        dispute.decided_at = timezone.now()
        dispute.deducted_amount = deducted_amount or 0
        dispute.save()

        if decision == DisputeDecision.FULL_REFUND:
            # 100% deposit refunded to renter
            _create_ledger(order, LedgerKind.DEPOSIT_RELEASE, -order.deposit, "Hoàn cọc 100% – tranh chấp")

        elif decision == DisputeDecision.PARTIAL_DEDUCTION:
            # Partial: deducted goes to owner, rest refunded
            refund = order.deposit - deducted_amount
            if refund > 0:
                _create_ledger(order, LedgerKind.DEPOSIT_RELEASE, -refund,
                               f"Hoàn cọc một phần ({refund:,} VND) – tranh chấp")
            if deducted_amount > 0:
                _create_ledger(order, LedgerKind.DEPOSIT_DEDUCT, -deducted_amount,
                               f"Khấu trừ cọc ({deducted_amount:,} VND) – bồi thường chủ đồ")

        elif decision == DisputeDecision.FULL_DEDUCTION:
            # 100% deposit goes to owner as compensation
            _create_ledger(order, LedgerKind.DEPOSIT_DEDUCT, -order.deposit,
                           "Khấu trừ cọc 100% – bồi thường chủ đồ")

        _transition(order, OrderStatus.COMPLETED, admin_user, f"Tranh chấp đã xử lý: {note}")
        _set_deadline(order, None)

        DisputeLog.objects.create(
            dispute=dispute,
            actor=admin_user,
            action="resolve",
            note=f"Quyết định: {dispute.get_decision_display()}. {note}",
        )

    return dispute


def expire_overdue(order):
    """Auto-cancel an order that has been in pending_owner past deadline."""
    with transaction.atomic():
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        if order.status != OrderStatus.PENDING_OWNER:
            return  # Already transitioned
        if order.deadline_at and timezone.now() > order.deadline_at:
            order.cancelled_reason = "Tự động huỷ – chủ đồ không phản hồi trong 15 phút."
            order.save(update_fields=["cancelled_reason", "updated_at"])
            _transition(order, OrderStatus.CANCELLED, None, "Tự động huỷ – hết thời gian chờ.")


def lazy_expire_check(order):
    """Called on every order read/write. Checks and auto-cancels if overdue."""
    if (order.status == OrderStatus.PENDING_OWNER
            and order.deadline_at
            and timezone.now() > order.deadline_at):
        expire_overdue(order)
        order.refresh_from_db()
