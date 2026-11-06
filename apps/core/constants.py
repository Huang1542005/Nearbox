"""
NearBox business constants — single source of truth.
All monetary values in VND (stored as BigIntegerField).
"""

# ── Deposit Tiers ──────────────────────────────────────────────────────
DEPOSIT_TIER_LOW = 200_000       # retail < 1,000,000
DEPOSIT_TIER_MID = 500_000       # retail 1,000,000 – 1,999,999
DEPOSIT_TIER_HIGH = 1_000_000    # retail 2,000,000 – 3,000,000

DEPOSIT_THRESHOLDS = [
    (1_000_000, DEPOSIT_TIER_LOW),
    (2_000_000, DEPOSIT_TIER_MID),
    (3_000_000, DEPOSIT_TIER_HIGH),
]

# ── Listing block ──────────────────────────────────────────────────────
MAX_RETAIL_PRICE = 3_000_000
BLOCKED_CATEGORIES = ["electronics"]  # slugs

# ── Pricing ────────────────────────────────────────────────────────────
SUGGESTED_PRICE_MIN_RATE = 0.07  # 7% of retail
SUGGESTED_PRICE_MAX_RATE = 0.08  # 8% of retail
ROUND_TO = 1_000                 # round to nearest 1,000 VND

# ── Fees ───────────────────────────────────────────────────────────────
PLATFORM_FEE = 5_000             # per order, charged to renter
COMMISSION_RATE = 0.15           # 15% of rental fee → NearBox
OWNER_PAYOUT_RATE = 0.85         # 85% of rental fee → owner

# ── Buildings ──────────────────────────────────────────────────────────
BUILDINGS = [f"S{i}" for i in range(1, 11)]

# ── Lobby Pickup Slots ─────────────────────────────────────────────────
LOBBY_SLOTS = [
    ("morning", "07:30 – 08:30"),
    ("evening", "18:30 – 20:30"),
]

# ── Order States ───────────────────────────────────────────────────────
class OrderStatus:
    PENDING_OWNER = "pending_owner"
    AWAITING_PAYMENT = "awaiting_payment"
    ESCROW_HELD = "escrow_held"
    HANDED_OVER = "handed_over"
    RETURNED = "returned"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"

    CHOICES = [
        (PENDING_OWNER, "Chờ chủ duyệt"),
        (AWAITING_PAYMENT, "Chờ thanh toán"),
        (ESCROW_HELD, "Đã giữ cọc"),
        (HANDED_OVER, "Đã giao"),
        (RETURNED, "Đã trả"),
        (COMPLETED, "Hoàn tất"),
        (DISPUTED, "Tranh chấp"),
        (CANCELLED, "Đã huỷ"),
    ]

# Valid state transitions: current_state → set of allowed next states
VALID_TRANSITIONS = {
    OrderStatus.PENDING_OWNER: {OrderStatus.AWAITING_PAYMENT, OrderStatus.CANCELLED},
    OrderStatus.AWAITING_PAYMENT: {OrderStatus.ESCROW_HELD, OrderStatus.CANCELLED},
    OrderStatus.ESCROW_HELD: {OrderStatus.HANDED_OVER, OrderStatus.CANCELLED},
    OrderStatus.HANDED_OVER: {OrderStatus.RETURNED, OrderStatus.DISPUTED},
    OrderStatus.RETURNED: {OrderStatus.COMPLETED, OrderStatus.DISPUTED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.DISPUTED: {OrderStatus.COMPLETED},
    OrderStatus.CANCELLED: set(),
}

# ── Item Status ────────────────────────────────────────────────────────
class ItemStatus:
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REJECTED = "rejected"
    HIDDEN = "hidden"

    CHOICES = [
        (PENDING_REVIEW, "Chờ duyệt"),
        (ACTIVE, "Đang hoạt động"),
        (REJECTED, "Bị từ chối"),
        (HIDDEN, "Đã ẩn"),
    ]

# ── Category Groups ───────────────────────────────────────────────────
CATEGORY_GROUPS = [
    ("repair_tools", "Dụng cụ sửa chữa"),
    ("cleaning", "Dụng cụ vệ sinh"),
    ("outdoor", "Dã ngoại"),
    ("small_appliances", "Đồ gia dụng nhỏ / Dụng cụ làm bánh"),
]

# ── Dispute Decisions ─────────────────────────────────────────────────
class DisputeDecision:
    FULL_REFUND = "full_refund"
    PARTIAL_DEDUCTION = "partial_deduction"
    FULL_DEDUCTION = "full_deduction"

    CHOICES = [
        (FULL_REFUND, "Hoàn cọc 100%"),
        (PARTIAL_DEDUCTION, "Khấu trừ một phần"),
        (FULL_DEDUCTION, "Khấu trừ toàn bộ"),
    ]

# ── Error Codes ────────────────────────────────────────────────────────
class ErrorCode:
    ORDER_INVALID_STATE = "ORDER_INVALID_STATE"
    ITEM_BLOCKED_HIGH_VALUE = "ITEM_BLOCKED_HIGH_VALUE"
    ITEM_BLOCKED_CATEGORY = "ITEM_BLOCKED_CATEGORY"
    OWNER_NOT_VERIFIED = "OWNER_NOT_VERIFIED"
    MISSING_CHECKIN_PHOTO = "MISSING_CHECKIN_PHOTO"
    MISSING_CHECKOUT_PHOTO = "MISSING_CHECKOUT_PHOTO"
    MISSING_WAIVER_CONSENT = "MISSING_WAIVER_CONSENT"
    INVALID_OTP = "INVALID_OTP"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ITEM_NOT_AVAILABLE = "ITEM_NOT_AVAILABLE"

# ── Ledger Entry Kinds ─────────────────────────────────────────────────
class LedgerKind:
    RENT_HOLD = "rent_hold"
    DEPOSIT_HOLD = "deposit_hold"
    PLATFORM_FEE = "platform_fee"
    DEPOSIT_RELEASE = "deposit_release"
    OWNER_PAYOUT = "owner_payout"
    COMMISSION = "commission"
    DEPOSIT_DEDUCT = "deposit_deduct"
    RISK_FUND = "risk_fund"

    CHOICES = [
        (RENT_HOLD, "Giữ tiền thuê"),
        (DEPOSIT_HOLD, "Giữ tiền cọc"),
        (PLATFORM_FEE, "Phí nền tảng"),
        (DEPOSIT_RELEASE, "Hoàn cọc"),
        (OWNER_PAYOUT, "Thanh toán chủ"),
        (COMMISSION, "Hoa hồng NearBox"),
        (DEPOSIT_DEDUCT, "Khấu trừ cọc"),
        (RISK_FUND, "Quỹ rủi ro"),
    ]

# ── Rental Durations ──────────────────────────────────────────────────
class RentalDuration:
    BLOCK_24H = "24h"
    COMBO_48H = "48h_weekend"

    CHOICES = [
        (BLOCK_24H, "24 giờ"),
        (COMBO_48H, "48 giờ cuối tuần"),
    ]

    MULTIPLIERS = {
        BLOCK_24H: 1.0,
        COMBO_48H: 1.5,
    }
