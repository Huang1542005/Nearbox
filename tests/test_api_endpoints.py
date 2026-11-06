import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Item
from apps.core.constants import ItemStatus
from tests.factories import AdminFactory, CategoryFactory, ItemFactory, OrderFactory, UserFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_auth_otp_flow(client):
    # Request OTP
    res = client.post("/api/v1/auth/request-otp/", {"phone": "0987654321"})
    assert res.status_code == 200

    # Verify OTP with mock debug code 000000
    res = client.post("/api/v1/auth/verify-otp/", {"phone": "0987654321", "otp": "000000"})
    assert res.status_code == 200
    assert "access" in res.data
    assert "refresh" in res.data

    # Use access token for /me/
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
    res_me = client.get("/api/v1/auth/me/")
    assert res_me.status_code == 200
    assert res_me.data["phone"] == "0987654321"


@pytest.mark.django_db
def test_items_same_building_first(client):
    user_s1 = UserFactory(building="S1")
    user_s2 = UserFactory(building="S2")

    item_s2 = ItemFactory(owner=user_s2, building="S2", name="Đồ toà S2")
    item_s1 = ItemFactory(owner=user_s1, building="S1", name="Đồ toà S1")

    client.force_authenticate(user=user_s1)
    res = client.get("/api/v1/items/")
    assert res.status_code == 200

    results = res.data.get("results", res.data)
    # The first item should be from S1 because user is in S1
    assert results[0]["id"] == item_s1.id


@pytest.mark.django_db
def test_price_suggestion_endpoint(client):
    user = UserFactory()
    client.force_authenticate(user=user)

    res = client.post("/api/v1/items/price-suggestion/", {
        "retail_price": 1_000_000,
        "category": "repair_tools",
    })
    assert res.status_code == 200
    assert res.data["suggested_min_price"] == 70_000
    assert res.data["suggested_max_price"] == 80_000
    assert res.data["deposit_tier"] == 500_000
    assert res.data["is_blocked"] is False


@pytest.mark.django_db
def test_unverified_owner_cannot_list_item(client):
    unverified_user = UserFactory(is_resident_verified=False)
    client.force_authenticate(user=unverified_user)
    cat = CategoryFactory()

    from PIL import Image
    import io
    from django.core.files.uploadedfile import SimpleUploadedFile

    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    photo = SimpleUploadedFile("p1.jpg", buf.read(), content_type="image/jpeg")

    res = client.post("/api/v1/items/", {
        "name": "Khoan mini",
        "category": cat.id,
        "retail_price": 500_000,
        "daily_price": 40_000,
        "photo_1": photo,
    }, format="multipart")

    assert res.status_code in (403, 422)


@pytest.mark.django_db
def test_wallet_endpoint(client):
    user = UserFactory()
    client.force_authenticate(user=user)

    res = client.get("/api/v1/wallet/")
    assert res.status_code == 200
    assert "balance" in res.data
    assert "monthly_earnings" in res.data
    assert "ledger_history" in res.data


@pytest.mark.django_db
def test_admin_dashboard_and_csv_exports(client):
    admin = AdminFactory()
    client.force_authenticate(user=admin)

    # Dashboard
    res = client.get("/api/v1/admin/dashboard/")
    assert res.status_code == 200
    assert "total_escrow_held" in res.data
    assert "orders_today" in res.data
    assert "open_disputes" in res.data

    # Export orders
    res_orders = client.get("/api/v1/admin/export/orders.csv")
    assert res_orders.status_code == 200
    assert res_orders["Content-Type"].startswith("text/csv")

    # Export events
    res_events = client.get("/api/v1/admin/export/events.csv")
    assert res_events.status_code == 200
    assert res_events["Content-Type"].startswith("text/csv")
