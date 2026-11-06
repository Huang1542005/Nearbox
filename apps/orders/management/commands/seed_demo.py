import io
import os
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.accounts.models import User
from apps.catalog.models import Category, Item
from apps.core.constants import (
    CATEGORY_GROUPS,
    ItemStatus,
    LedgerKind,
    OrderStatus,
    RentalDuration,
)
from apps.core.utils import calculate_order_breakdown, get_deposit_tier
from apps.disputes.models import Dispute, DisputeLog
from apps.escrow.models import LedgerEntry
from apps.orders.models import HandoverPhoto, Order, OrderEvent
from apps.orders.views import process_handover_photo


def create_placeholder_image(text: str, bg_color=(41, 128, 185), size=(600, 400)) -> ContentFile:
    img = Image.new("RGB", size, color=bg_color)
    draw = ImageDraw.Draw(img)

    # Draw border
    draw.rectangle([10, 10, size[0] - 10, size[1] - 10], outline=(255, 255, 255), width=3)

    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Draw text centered
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((size[0] - w) / 2, (size[1] - h) / 2), text, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return ContentFile(buf.read(), name=f"{text.replace(' ', '_')[:20]}.jpg")


class Command(BaseCommand):
    help = "Seed demo data for NearBox MVP (idempotent)."

    def handle(self, *args, **options):
        self.stdout.write("Khởi tạo dữ liệu mẫu NearBox...")

        # ── 1. Create Demo Users ──────────────────────────────────────
        admin_user, _ = User.objects.get_or_create(
            phone="0900000000",
            defaults={
                "full_name": "NearBox Admin (Concierge)",
                "building": "S1",
                "unit_number": "1001",
                "is_resident_verified": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_user.set_password("admin123")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        renter_user, _ = User.objects.get_or_create(
            phone="0901000001",
            defaults={
                "full_name": "Nguyễn Văn Thuê (Renter)",
                "building": "S1",
                "unit_number": "0802",
                "is_resident_verified": True,
            },
        )

        owner_verified, _ = User.objects.get_or_create(
            phone="0902000002",
            defaults={
                "full_name": "Trần Thị Chủ Đồ (Verified Owner)",
                "building": "S2",
                "unit_number": "1205",
                "is_resident_verified": True,
            },
        )

        owner_pending, _ = User.objects.get_or_create(
            phone="0903000003",
            defaults={
                "full_name": "Lê Văn Chờ Duyệt (Pending Owner)",
                "building": "S3",
                "unit_number": "0410",
                "is_resident_verified": False,
            },
        )
        if not owner_pending.resident_proof:
            owner_pending.resident_proof.save(
                "proof_s3_0410.jpg",
                create_placeholder_image("Căn hộ S3-0410 Hợp đồng", bg_color=(52, 73, 94)),
                save=True,
            )

        self.stdout.write(self.style.SUCCESS("✓ 4 tài khoản người dùng đã sẵn sàng."))

        # ── 2. Create Categories ──────────────────────────────────────
        cat_map = {}
        for group_key, group_name in CATEGORY_GROUPS:
            cat, _ = Category.objects.get_or_create(
                slug=group_key,
                defaults={"name": group_name, "group": group_key},
            )
            cat_map[group_key] = cat

        self.stdout.write(self.style.SUCCESS("✓ 4 nhóm danh mục đã sẵn sàng."))

        # ── 3. Create at least 12 items ───────────────────────────────
        items_spec = [
            # Repair tools
            ("Máy khoan búa Bosch GSB 550", "repair_tools", 1_200_000, 90_000, "S2", "Máy khoan động lực công suất 550W kèm bộ mũi khoan cơ bản."),
            ("Thang nhôm chữ A Nikita 2m", "repair_tools", 950_000, 70_000, "S1", "Thang nhôm khóa tự động chắc chắn, tải trọng 150kg."),
            ("Xe đẩy hàng gấp gọn 150kg", "repair_tools", 800_000, 60_000, "S3", "Xe đẩy 4 bánh gấp gọn dễ bỏ cốp ô tô và thang máy."),

            # Cleaning
            ("Máy hút bụi đệm giường Deerma CM800", "cleaning", 750_000, 55_000, "S2", "Diệt khuẩn UV và rung đập bụi mịn đệm sofa hiệu quả."),
            ("Máy rửa xe áp lực cao Karcher K2", "cleaning", 2_400_000, 170_000, "S4", "Rửa xe máy, sàn ban công và cửa kính cực sạch."),
            ("Cây lau nhà hơi nước Lock&Lock", "cleaning", 1_100_000, 80_000, "S5", "Khử trùng nhiệt độ cao cho sàn gạch và sàn gỗ."),

            # Outdoor
            ("Lều cắm trại 4 người Naturehike", "outdoor", 1_600_000, 120_000, "S2", "Chống mưa tốt, 2 lớp thoáng khí cho công viên hoặc cắm trại hồ."),
            ("Bếp nướng than hoa du lịch gấp gọn", "outdoor", 600_000, 45_000, "S6", "Thép không gỉ, vỉ nướng inox dễ lau rửa."),
            ("Bộ bàn ghế dã ngoại xếp gọn 4 ghế", "outdoor", 1_300_000, 95_000, "S7", "Gấp lại như chiếc cặp xách nhẹ nhàng."),

            # Small appliances
            ("Máy đánh trứng cầm tay Philips", "small_appliances", 550_000, 40_000, "S1", "Công suất 300W với 5 tốc độ đánh kem làm bánh."),
            ("Nồi chiên không dầu Tefal 4.2L", "small_appliances", 2_200_000, 160_000, "S8", "Dung tích lớn nướng gà nguyên con."),
            ("Máy ép chậm Philips Viva Collection", "small_appliances", 2_800_000, 200_000, "S9", "Ép kiệt bã giữ trọn vitamin cho nước ép trái cây."),
        ]

        created_items = []
        for name, cat_key, retail, daily, bld, desc in items_spec:
            dep_tier = get_deposit_tier(retail)
            item, created = Item.objects.get_or_create(
                name=name,
                defaults={
                    "owner": owner_verified,
                    "category": cat_map[cat_key],
                    "retail_price": retail,
                    "daily_price": daily,
                    "deposit_tier": dep_tier,
                    "building": bld,
                    "description": desc,
                    "status": ItemStatus.ACTIVE,
                },
            )
            if not item.photo_1:
                item.photo_1.save(
                    f"{item.id}_photo1.jpg",
                    create_placeholder_image(name[:25], bg_color=(39, 174, 96)),
                    save=False,
                )
                item.photo_2.save(
                    f"{item.id}_photo2.jpg",
                    create_placeholder_image(f"{name[:20]} Detail", bg_color=(46, 204, 113)),
                    save=False,
                )
                item.save()
            created_items.append(item)

        self.stdout.write(self.style.SUCCESS(f"✓ {len(created_items)} sản phẩm đã sẵn sàng."))

        # ── 4. Seed 1 Sample Dispute (Máy khoan búa Bosch) ─────────────
        drill_item = Item.objects.get(name="Máy khoan búa Bosch GSB 550")
        dispute_order_code = "NBX-DISPUTE-01"
        dispute_order, order_created = Order.objects.get_or_create(
            code=dispute_order_code,
            defaults={
                "item": drill_item,
                "renter": renter_user,
                "owner": owner_verified,
                "status": OrderStatus.DISPUTED,
                "rental_duration": RentalDuration.BLOCK_24H,
                "pickup_slot": "morning",
                "pickup_time": timezone.now() - timedelta(days=2),
                "daily_price": drill_item.daily_price,
                "rental_fee": drill_item.daily_price,
                "deposit": drill_item.deposit_tier,
                "platform_fee": 5_000,
                "total_amount": drill_item.daily_price + drill_item.deposit_tier + 5_000,
                "commission": int(drill_item.daily_price * 0.15),
                "owner_payout": int(drill_item.daily_price * 0.85),
                "risk_fund": 800,
                "liability_waiver_accepted": True,
            },
        )

        if order_created:
            # Events
            OrderEvent.objects.create(order=dispute_order, actor=renter_user, from_status=OrderStatus.PENDING_OWNER, to_status=OrderStatus.PENDING_OWNER, note="Tạo đơn thuê")
            OrderEvent.objects.create(order=dispute_order, actor=owner_verified, from_status=OrderStatus.PENDING_OWNER, to_status=OrderStatus.AWAITING_PAYMENT, note="Chủ đồ duyệt")
            OrderEvent.objects.create(order=dispute_order, actor=admin_user, from_status=OrderStatus.AWAITING_PAYMENT, to_status=OrderStatus.ESCROW_HELD, note="Admin xác nhận thanh toán")
            OrderEvent.objects.create(order=dispute_order, actor=renter_user, from_status=OrderStatus.ESCROW_HELD, to_status=OrderStatus.HANDED_OVER, note="Nhận đồ tại sảnh")
            OrderEvent.objects.create(order=dispute_order, actor=owner_verified, from_status=OrderStatus.HANDED_OVER, to_status=OrderStatus.DISPUTED, note="Mũi khoan bị gãy và kẹt đầu kẹp")

            # Photos
            checkin_file = create_placeholder_image("Checkin Máy khoan nguyên vẹn", bg_color=(41, 128, 185))
            proc_file, sha, taken = process_handover_photo(checkin_file, dispute_order.code)
            HandoverPhoto.objects.create(
                order=dispute_order,
                photo_type="checkin",
                image=proc_file,
                taken_at=timezone.now() - timedelta(days=2),
                uploaded_by=renter_user,
                sha256=sha,
            )

            checkout_file = create_placeholder_image("Checkout Mũi khoan bị gãy", bg_color=(192, 57, 43))
            proc_file2, sha2, taken2 = process_handover_photo(checkout_file, dispute_order.code)
            HandoverPhoto.objects.create(
                order=dispute_order,
                photo_type="checkout",
                image=proc_file2,
                taken_at=timezone.now() - timedelta(days=1),
                uploaded_by=owner_verified,
                sha256=sha2,
            )

            # Dispute record
            dispute, _ = Dispute.objects.get_or_create(
                order=dispute_order,
                defaults={
                    "opened_by": owner_verified,
                    "reason": "Mũi khoan bê tông 8mm bị gãy và máy bị kẹt đầu kẹp không tháo được.",
                    "status": Dispute.STATUS_OPEN,
                },
            )
            DisputeLog.objects.get_or_create(
                dispute=dispute,
                actor=owner_verified,
                action="open",
                defaults={"note": dispute.reason},
            )

            # Ledger hold
            LedgerEntry.objects.create(order=dispute_order, kind=LedgerKind.RENT_HOLD, amount=dispute_order.rental_fee, description="Giữ tiền thuê")
            LedgerEntry.objects.create(order=dispute_order, kind=LedgerKind.DEPOSIT_HOLD, amount=dispute_order.deposit, description="Giữ tiền cọc")
            LedgerEntry.objects.create(order=dispute_order, kind=LedgerKind.PLATFORM_FEE, amount=dispute_order.platform_fee, description="Phí nền tảng")

        self.stdout.write(self.style.SUCCESS("✓ 1 đơn tranh chấp mẫu đã sẵn sàng."))

        # ── 5. Seed 1 Late Return Order (Thang nhôm) ───────────────────
        ladder_item = Item.objects.get(name="Thang nhôm chữ A Nikita 2m")
        late_order_code = "NBX-LATE-02"
        late_order, late_created = Order.objects.get_or_create(
            code=late_order_code,
            defaults={
                "item": ladder_item,
                "renter": renter_user,
                "owner": owner_verified,
                "status": OrderStatus.COMPLETED,
                "rental_duration": RentalDuration.BLOCK_24H,
                "pickup_slot": "morning",
                "pickup_time": timezone.now() - timedelta(days=3),
                "daily_price": ladder_item.daily_price,
                "rental_fee": ladder_item.daily_price,
                "deposit": ladder_item.deposit_tier,
                "platform_fee": 5_000,
                "total_amount": ladder_item.daily_price + ladder_item.deposit_tier + 5_000,
                "commission": int(ladder_item.daily_price * 0.15),
                "owner_payout": int(ladder_item.daily_price * 0.85),
                "risk_fund": 600,
                "liability_waiver_accepted": True,
            },
        )

        if late_created:
            # Events
            t0 = timezone.now() - timedelta(days=3)
            OrderEvent.objects.create(order=late_order, actor=renter_user, from_status=OrderStatus.PENDING_OWNER, to_status=OrderStatus.PENDING_OWNER, note="Tạo đơn", created_at=t0)
            OrderEvent.objects.create(order=late_order, actor=owner_verified, from_status=OrderStatus.PENDING_OWNER, to_status=OrderStatus.AWAITING_PAYMENT, note="Duyệt đơn", created_at=t0 + timedelta(minutes=5))
            OrderEvent.objects.create(order=late_order, actor=admin_user, from_status=OrderStatus.AWAITING_PAYMENT, to_status=OrderStatus.ESCROW_HELD, note="Admin xác nhận thanh toán", created_at=t0 + timedelta(minutes=10))
            OrderEvent.objects.create(order=late_order, actor=renter_user, from_status=OrderStatus.ESCROW_HELD, to_status=OrderStatus.HANDED_OVER, note="Nhận đồ tại sảnh", created_at=t0 + timedelta(minutes=25))
            OrderEvent.objects.create(order=late_order, actor=renter_user, from_status=OrderStatus.HANDED_OVER, to_status=OrderStatus.RETURNED, note="Trả đồ trễ 2 giờ do kẹt xe", created_at=t0 + timedelta(hours=26))
            OrderEvent.objects.create(order=late_order, actor=owner_verified, from_status=OrderStatus.RETURNED, to_status=OrderStatus.COMPLETED, note="Chủ đồ thông cảm không tính phạt, hoàn tất", created_at=t0 + timedelta(hours=27))

            # Photos
            p_checkin = create_placeholder_image("Checkin Thang Nhôm", bg_color=(39, 174, 96))
            f1, s1, _ = process_handover_photo(p_checkin, late_order.code)
            HandoverPhoto.objects.create(
                order=late_order,
                photo_type="checkin",
                image=f1,
                taken_at=t0 + timedelta(minutes=25),
                uploaded_by=renter_user,
                sha256=s1,
            )

            p_checkout = create_placeholder_image("Checkout Thang Nhôm Hoàn Hảo", bg_color=(46, 204, 113))
            f2, s2, _ = process_handover_photo(p_checkout, late_order.code)
            HandoverPhoto.objects.create(
                order=late_order,
                photo_type="checkout",
                image=f2,
                taken_at=t0 + timedelta(hours=26),
                uploaded_by=renter_user,
                sha256=s2,
            )

            # Complete ledger lifecycle
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.RENT_HOLD, amount=late_order.rental_fee, description="Giữ tiền thuê")
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.DEPOSIT_HOLD, amount=late_order.deposit, description="Giữ tiền cọc")
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.PLATFORM_FEE, amount=late_order.platform_fee, description="Phí nền tảng")
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.OWNER_PAYOUT, amount=-late_order.owner_payout, description="Thanh toán chủ đồ")
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.COMMISSION, amount=-late_order.commission, description="Hoa hồng NearBox")
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.RISK_FUND, amount=late_order.risk_fund, description="Quỹ rủi ro")
            LedgerEntry.objects.create(order=late_order, kind=LedgerKind.DEPOSIT_RELEASE, amount=-late_order.deposit, description="Hoàn cọc 100%")

        self.stdout.write(self.style.SUCCESS("✓ 1 đơn trả trễ mẫu đã sẵn sàng."))
        self.stdout.write(self.style.SUCCESS("==> Hoàn tất khởi tạo dữ liệu mẫu NearBox!"))
