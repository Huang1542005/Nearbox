from django.urls import path

from . import views

app_name = "escrow"

urlpatterns = [
    path("wallet/", views.WalletView.as_view(), name="wallet"),
]
