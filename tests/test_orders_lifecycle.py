import pytest
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
import io

from apps.core.constants import ErrorCode, LedgerKind, OrderStatus
from apps.core.exceptions import BusinessError
from apps.orders import services
from apps.orders.models import HandoverPhoto, Order, OrderEvent
from tests.factories import AdminFactory, ItemFactory, OrderFactory, UserFactory


def make_test_photo(order, photo_type, uploader):
    img = Image.new("RGB", (50, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    file = SimpleUploadedFile("test.jpg", buf.read(), content_type="image/jpeg")
    return HandoverPhoto.objects.create(
        order=order,
        photo_type=photo_type,
        image=file,
        taken_at=timezone.now(),
        uploaded_by=uploader,
        sha256="test-sha256",
    )


@pytest.mark.django_db
def test_full_order_lifecycle():
    owner = UserFactory(building="S2")
    renter = UserFactory(building="S1")
    admin = AdminFactory()
    item = ItemFactory(owner=owner, daily_price=70_000, deposit_tier=200_000)

    # 1. Create order
    order = OrderFactory(
        item=item,
        owner=owner,
        renter=renter,
        status=OrderStatus.PENDING_OWNER,
        rental_fee=70_000,
        deposit=200_000,
        platform_fee=5_000,
        total_amount=275_000,
        commission=10_500,
        owner_payout=59_500,
        risk_fund=620,
    )

    # 2. Renter cannot approve, only owner can
    with pytest.raises(BusinessError) as exc_info:
        services.approve_order(order, renter)
    assert exc_info.value.status_code == 403

    # Owner approves -> awaiting_payment
    services.approve_order(order, owner)
    order.refresh_from_db()
    assert order.status == OrderStatus.AWAITING_PAYMENT

    # 3. Non-admin cannot confirm payment
    with pytest.raises(BusinessError) as exc_info:
        services.admin_confirm_payment(order, renter)
    assert exc_info.value.status_code == 403

    # Admin confirms payment -> escrow_held
    services.admin_confirm_payment(order, admin)
    order.refresh_from_db()
    assert order.status == OrderStatus.ESCROW_HELD

    # Verify ledger entries for escrow
    assert order.ledger_entries.filter(kind=LedgerKind.RENT_HOLD, amount=70_000).exists()
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_HOLD, amount=200_000).exists()
    assert order.ledger_entries.filter(kind=LedgerKind.PLATFORM_FEE, amount=5_000).exists()

    # 4. Handover without check-in photo fails
    with pytest.raises(BusinessError) as exc_info:
        services.confirm_handover(order, renter, liability_waiver_consent=True)
    assert exc_info.value.error_code == ErrorCode.MISSING_CHECKIN_PHOTO

    # Handover with photo but no waiver consent fails
    make_test_photo(order, "checkin", renter)
    with pytest.raises(BusinessError) as exc_info:
        services.confirm_handover(order, renter, liability_waiver_consent=False)
    assert exc_info.value.error_code == ErrorCode.MISSING_WAIVER_CONSENT

    # Handover succeeds
    services.confirm_handover(order, renter, liability_waiver_consent=True)
    order.refresh_from_db()
    assert order.status == OrderStatus.HANDED_OVER
    assert order.liability_waiver_accepted is True

    # Verify ledger entries on handover: owner payout and commission
    assert order.ledger_entries.filter(kind=LedgerKind.OWNER_PAYOUT, amount=-59_500).exists()
    assert order.ledger_entries.filter(kind=LedgerKind.COMMISSION, amount=-10_500).exists()

    # 5. Return without checkout photo fails
    with pytest.raises(BusinessError) as exc_info:
        services.submit_return(order, renter)
    assert exc_info.value.error_code == ErrorCode.MISSING_CHECKOUT_PHOTO

    # Upload checkout photo and submit return -> returned
    make_test_photo(order, "checkout", renter)
    services.submit_return(order, renter)
    order.refresh_from_db()
    assert order.status == OrderStatus.RETURNED

    # 6. Owner confirms return -> completed, deposit release
    services.confirm_return(order, owner)
    order.refresh_from_db()
    assert order.status == OrderStatus.COMPLETED
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_RELEASE, amount=-200_000).exists()


@pytest.mark.django_db
def test_expire_overdue_orders():
    order = OrderFactory(
        status=OrderStatus.PENDING_OWNER,
        deadline_at=timezone.now() - timedelta(minutes=1),
    )
    services.expire_overdue(order)
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert "Tự động huỷ" in order.cancelled_reason


@pytest.mark.django_db
def test_cancel_at_lobby_with_refund():
    admin = AdminFactory()
    order = OrderFactory(
        status=OrderStatus.AWAITING_PAYMENT,
        rental_fee=70_000,
        deposit=200_000,
        platform_fee=5_000,
    )
    services.admin_confirm_payment(order, admin)
    order.refresh_from_db()
    assert order.status == OrderStatus.ESCROW_HELD

    # Cancel at lobby
    services.cancel_at_lobby(order, order.renter, note="Không gặp được chủ")
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED

    # Check refunds in ledger
    assert order.ledger_entries.filter(kind=LedgerKind.DEPOSIT_RELEASE, amount=-200_000).exists()
    assert order.ledger_entries.filter(kind=LedgerKind.RENT_HOLD, amount=-70_000).exists()
    assert order.ledger_entries.filter(kind=LedgerKind.PLATFORM_FEE, amount=-5_000).exists()
