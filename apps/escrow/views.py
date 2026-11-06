from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Wallet
from .serializers import WalletSerializer


class WalletView(RetrieveAPIView):
    """GET /api/v1/wallet/ — Xem số dư ví, thu nhập tháng và lịch sử giao dịch."""

    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        wallet, _created = Wallet.objects.get_or_create(user=self.request.user)
        return wallet
