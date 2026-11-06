from django.urls import path

from . import views

app_name = "disputes"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),

    # Resident verification review
    path("residents/", views.ResidentListView.as_view(), name="resident-list"),
    path("residents/<int:pk>/approve/", views.ResidentApproveView.as_view(), name="resident-approve"),
    path("residents/<int:pk>/reject/", views.ResidentRejectView.as_view(), name="resident-reject"),

    # Item review
    path("items/pending/", views.PendingItemListView.as_view(), name="item-pending-list"),
    path("items/pending/<int:pk>/approve/", views.PendingItemApproveView.as_view(), name="item-pending-approve"),
    path("items/pending/<int:pk>/reject/", views.PendingItemRejectView.as_view(), name="item-pending-reject"),

    # Order payment confirmation
    path("orders/<int:pk>/confirm-payment/", views.AdminConfirmPaymentView.as_view(), name="order-confirm-payment"),

    # Disputes
    path("disputes/", views.DisputeListView.as_view(), name="dispute-list"),
    path("disputes/<int:pk>/", views.DisputeDetailView.as_view(), name="dispute-detail"),
    path("disputes/<int:pk>/resolve/", views.DisputeResolveView.as_view(), name="dispute-resolve"),

    # CSV exports
    path("export/orders.csv", views.ExportOrdersCSVView.as_view(), name="export-orders-csv"),
    path("export/events.csv", views.ExportEventsCSVView.as_view(), name="export-events-csv"),
]
