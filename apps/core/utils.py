import math
from apps.core.constants import (
    SUGGESTED_PRICE_MIN_RATE, SUGGESTED_PRICE_MAX_RATE, ROUND_TO,
    DEPOSIT_THRESHOLDS, MAX_RETAIL_PRICE, BLOCKED_CATEGORIES,
    PLATFORM_FEE, COMMISSION_RATE, OWNER_PAYOUT_RATE,
)
from django.conf import settings


def round_vnd(amount: int) -> int:
    """Round to nearest 1,000 VND."""
    return int(math.ceil(amount / ROUND_TO) * ROUND_TO)


def suggested_price_range(retail_price: int) -> dict:
    """Return min/max daily rental price suggestion."""
    min_price = round_vnd(int(retail_price * SUGGESTED_PRICE_MIN_RATE))
    max_price = round_vnd(int(retail_price * SUGGESTED_PRICE_MAX_RATE))
    return {"min_daily_price": min_price, "max_daily_price": max_price}


def get_deposit_tier(retail_price: int) -> int | None:
    """Auto-assign deposit tier by retail price. Returns None if blocked."""
    for threshold, tier in DEPOSIT_THRESHOLDS:
        if retail_price < threshold:
            return tier
    # If retail_price == MAX_RETAIL_PRICE, use the highest tier
    if retail_price == MAX_RETAIL_PRICE:
        return DEPOSIT_THRESHOLDS[-1][1]
    return None


def is_listing_blocked(retail_price: int, category_slug: str | None = None) -> dict | None:
    """Check if an item should be blocked. Returns reason dict or None."""
    if retail_price > MAX_RETAIL_PRICE:
        return {
            "blocked": True,
            "reason": f"Giá trị sản phẩm vượt quá {MAX_RETAIL_PRICE:,} VND. "
                      "Vui lòng liên hệ admin để được hỗ trợ.",
            "code": "ITEM_BLOCKED_HIGH_VALUE",
        }
    if category_slug and category_slug in BLOCKED_CATEGORIES:
        return {
            "blocked": True,
            "reason": "Danh mục này hiện chưa được hỗ trợ cho thuê trên NearBox.",
            "code": "ITEM_BLOCKED_CATEGORY",
        }
    return None


def calculate_order_breakdown(daily_price: int, duration_multiplier: float, deposit: int) -> dict:
    """Calculate the full price breakdown for an order."""
    rental_fee = round_vnd(int(daily_price * duration_multiplier))
    commission = round_vnd(int(rental_fee * COMMISSION_RATE))
    owner_payout = rental_fee - commission
    risk_fund_rate = getattr(settings, "RISK_FUND_RATE", 0.04)
    nearbox_revenue = commission + PLATFORM_FEE
    risk_fund = round_vnd(int(nearbox_revenue * risk_fund_rate))
    total_renter_pays = rental_fee + deposit + PLATFORM_FEE

    return {
        "rental_fee": rental_fee,
        "deposit": deposit,
        "platform_fee": PLATFORM_FEE,
        "total_renter_pays": total_renter_pays,
        "commission": commission,
        "owner_payout": owner_payout,
        "risk_fund": risk_fund,
        "nearbox_revenue": nearbox_revenue,
    }
