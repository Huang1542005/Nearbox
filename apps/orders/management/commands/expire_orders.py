from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.constants import OrderStatus
from apps.orders import services
from apps.orders.models import Order


class Command(BaseCommand):
    help = "Tự động huỷ các đơn hàng ở trạng thái 'Chờ chủ duyệt' quá 15 phút."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_orders = Order.objects.filter(
            status=OrderStatus.PENDING_OWNER,
            deadline_at__isnull=False,
            deadline_at__lte=now,
        )

        count = 0
        for order in expired_orders:
            try:
                services.expire_overdue(order)
                count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Đã huỷ đơn quá hạn: {order.code}")
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Lỗi khi huỷ đơn {order.code}: {e}")
                )

        if count == 0:
            self.stdout.write("Không có đơn hàng nào quá hạn.")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Đã xử lý xong {count} đơn hàng quá hạn.")
            )
