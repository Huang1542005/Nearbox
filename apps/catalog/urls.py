from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("items", views.ItemViewSet, basename="item")
router.register("rental-requests", views.RentalRequestViewSet, basename="rental-request")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "rental-requests/<int:rental_request_id>/quotes/",
        views.QuoteCreateView.as_view(),
        name="quote-create",
    ),
]
