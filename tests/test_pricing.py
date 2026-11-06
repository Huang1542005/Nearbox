import pytest
from apps.core.constants import (
    DEPOSIT_TIER_HIGH,
    DEPOSIT_TIER_LOW,
    DEPOSIT_TIER_MID,
    ErrorCode,
)
from apps.core.utils import (
    calculate_order_breakdown,
    get_deposit_tier,
    is_listing_blocked,
    round_vnd,
    suggested_price_range,
)


def test_round_vnd():
    assert round_vnd(1234) == 1000
    assert round_vnd(1500) == 2000
    assert round_vnd(1890) == 2000
    assert round_vnd(70000) == 70000


def test_suggested_price_range():
    # Retail = 1,000,000 VND -> 7% = 70,000; 8% = 80,000
    min_p, max_p = suggested_price_range(1_000_000)
    assert min_p == 70_000
    assert max_p == 80_000

    # Retail = 550,000 VND -> 7% = 38,500 -> 39,000; 8% = 44,000
    min_p, max_p = suggested_price_range(550_000)
    assert min_p == 39_000
    assert max_p == 44_000


def test_deposit_tiers():
    # < 1,000,000 -> 200k
    assert get_deposit_tier(500_000) == DEPOSIT_TIER_LOW
    assert get_deposit_tier(999_999) == DEPOSIT_TIER_LOW

    # 1,000,000 - 1,999,999 -> 500k
    assert get_deposit_tier(1_000_000) == DEPOSIT_TIER_MID
    assert get_deposit_tier(1_500_000) == DEPOSIT_TIER_MID
    assert get_deposit_tier(1_999_999) == DEPOSIT_TIER_MID

    # 2,000,000 - 3,000,000 -> 1M
    assert get_deposit_tier(2_000_000) == DEPOSIT_TIER_HIGH
    assert get_deposit_tier(3_000_000) == DEPOSIT_TIER_HIGH


def test_listing_blocked():
    # Retail > 3,000,000
    blocked, reason, code = is_listing_blocked(3_500_000, "repair_tools")
    assert blocked is True
    assert code == ErrorCode.ITEM_BLOCKED_HIGH_VALUE

    # Electronics
    blocked, reason, code = is_listing_blocked(1_500_000, "electronics")
    assert blocked is True
    assert code == ErrorCode.ITEM_BLOCKED_CATEGORY

    # Normal valid item
    blocked, reason, code = is_listing_blocked(1_200_000, "repair_tools")
    assert blocked is False
    assert reason == ""
    assert code == ""


def test_reference_example_order_breakdown():
    """
    Reference example:
    70,000 VND/day x 1.5 days = 105,000 VND GMV
    -> owner 89,250 VND (85%)
    -> NearBox commission 15,750 VND (15%) + 5,000 fee = 20,750 VND revenue.
    Renter pays: 105,000 (rental fee) + deposit (e.g. 200,000) + 5,000 (platform fee) = 310,000 VND.
    """
    daily_price = 70_000
    duration_multiplier = 1.5
    deposit = 200_000

    b = calculate_order_breakdown(daily_price, duration_multiplier, deposit)

    assert b["rental_fee"] == 105_000
    assert b["deposit"] == 200_000
    assert b["platform_fee"] == 5_000
    assert b["total_renter_pays"] == 310_000

    assert b["commission"] == 15_750
    assert b["owner_payout"] == 89_250
    assert b["nearbox_revenue"] == 20_750
    assert b["risk_fund"] == round_vnd(int(20_750 * 0.04))
