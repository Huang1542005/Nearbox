from django.db.models import Case, When, Value, IntegerField
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.constants import ItemStatus
from .models import Category, Item, Quote, RentalRequest
from .serializers import (
    CategorySerializer,
    ItemCreateSerializer,
    ItemDetailSerializer,
    ItemListSerializer,
    PriceSuggestionSerializer,
    QuoteSerializer,
    RentalRequestSerializer,
)


# ── Item ViewSet ──────────────────────────────────────────────────────


class ItemViewSet(viewsets.ModelViewSet):
    """CRUD sản phẩm cho thuê."""

    queryset = Item.objects.select_related("owner", "category").all()
    filterset_fields = ["building", "category__slug", "status"]
    search_fields = ["name", "description"]

    def get_serializer_class(self):
        if self.action == "create":
            return ItemCreateSerializer
        if self.action == "retrieve":
            return ItemDetailSerializer
        return ItemListSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_authenticated and user.building:
            # Same-building items first
            qs = qs.annotate(
                same_building=Case(
                    When(building=user.building, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
            ).order_by("same_building", "-created_at")

        return qs

    @action(
        detail=False,
        methods=["post"],
        url_path="price-suggestion",
        permission_classes=[AllowAny],
        serializer_class=PriceSuggestionSerializer,
    )
    def price_suggestion(self, request):
        """Gợi ý giá thuê dựa trên giá bán lẻ."""
        serializer = PriceSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data["result"])


# ── Rental Request ViewSet ────────────────────────────────────────────


class RentalRequestViewSet(viewsets.ModelViewSet):
    """CRUD yêu cầu thuê đồ."""

    queryset = RentalRequest.objects.select_related("requester", "category").all()
    serializer_class = RentalRequestSerializer
    permission_classes = [IsAuthenticated]


# ── Quote Create View ─────────────────────────────────────────────────


class QuoteCreateView(generics.CreateAPIView):
    """Tạo báo giá cho một yêu cầu thuê."""

    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        rental_request = generics.get_object_or_404(
            RentalRequest, pk=self.kwargs["rental_request_id"],
        )
        serializer.save(
            quoted_by=self.request.user,
            rental_request=rental_request,
        )
