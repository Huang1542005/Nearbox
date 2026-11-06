from django.urls import path

from apps.accounts.views import (
    RequestOTPView,
    ResidentProofView,
    TokenRefreshView,
    UserMeView,
    VerifyOTPView,
)

app_name = "accounts"

urlpatterns = [
    path("request-otp/", RequestOTPView.as_view(), name="request-otp"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", UserMeView.as_view(), name="user-me"),
    path("me/resident-proof/", ResidentProofView.as_view(), name="resident-proof"),
]
