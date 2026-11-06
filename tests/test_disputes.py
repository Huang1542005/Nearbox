import pytest
from apps.core.constants import DisputeDecision, LedgerKind, OrderStatus
from apps.core.exceptions import BusinessError
from apps.disputes.models import Dispute
from apps.orders import services
from tests.factories import AdminFactory, ItemFactory, OrderFactory, UserFactory


@pytest.mark.django_db
def test_dispute_full_refund():
    admin = AdminFactory()
    order = OrderFactory(
        status=OrderStatus.HANDED_OVER,
        deposit=500_000,
    )

    dispute = services.open_dispute(order, order.renter, reason="Đồ bị hư từ trước")
    order.refresh_from_db()
    assert order.status == OrderStatus.DISPUTED
    assert dispute.status == Dispute.STATUS_OPEN
    assert dispute.logs.count() == 1

    # Admin resolves with full refund
    services.resolve_dispute(
        dispute=dispute,
        decision=DisputeDecision.FULL_REFUND,
        deducted_amount=0,
        admin_user=admin,
        note="Đồ lỗi do chủ không báo trước",
    )

    dispute.refresh_from_db()
    order.refresh_from_db()
    assert dispute.status == Dispute.STATUS_RESOLVED
    assert dispute.decision == DisputeDecision.FULL_REFUND
    assert order.status == OrderStatus.COMPLETED
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_RELEASE, amount=-500_000).exists()


@pytest.mark.django_db
def test_dispute_partial_deduction():
    admin = AdminFactory()
    order = OrderFactory(
        status=OrderStatus.RETURNED,
        deposit=500_000,
    )

    dispute = services.open_dispute(order, order.owner, reason="Mất phụ kiện nhỏ")
    # Resolve with 200,000 deduction, 300,000 refund
    services.resolve_dispute(
        dispute=dispute,
        decision=DisputeDecision.PARTIAL_DEDUCTION,
        deducted_amount=200_000,
        admin_user=admin,
        note="Bồi thường tiền phụ kiện",
    )

    order.refresh_from_db()
    assert order.status == OrderStatus.COMPLETED
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_DEDUCT, amount=-200_000).exists()
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_RELEASE, amount=-300_000).exists()


@pytest.mark.django_db
def test_dispute_full_deduction():
    admin = AdminFactory()
    order = OrderFactory(
        status=OrderStatus.RETURNED,
        deposit=500_000,
    )

    dispute = services.open_dispute(order, order.owner, reason="Làm vỡ nát đồ")
    services.resolve_dispute(
        dispute=dispute,
        decision=DisputeDecision.FULL_DEDUCTION,
        deducted_amount=500_000,
        admin_user=admin,
        note="Bồi thường 100% tiền cọc",
    )

    order.refresh_from_db()
    assert order.status == OrderStatus.COMPLETED
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_DEDUCT, amount=-500_000).exists()
