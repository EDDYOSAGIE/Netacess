from django.contrib import admin
from django.urls import path

from config.views import health
from apps.adminops import views as ops
from apps.access_codes.views import MyCodesView
from apps.sms.views import OTPSendView, OTPVerifyView
from apps.notifications.views import MarkRead, NotificationList
from apps.orders.views import TransactionList
from apps.payments.views import CreateOrderView, FlutterwaveWebhook, PaymentDetailView
from apps.plans.me import MeView
from apps.plans.views import PlanList

urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("api/auth/otp/send", OTPSendView.as_view()),
    path("api/auth/otp/request", OTPSendView.as_view()),
    path("api/auth/otp/verify", OTPVerifyView.as_view()),
    path("api/plans", PlanList.as_view()),
    path("api/orders", CreateOrderView.as_view()),
    path("api/payments/<uuid:pk>", PaymentDetailView.as_view()),
    path("api/webhooks/flutterwave", FlutterwaveWebhook.as_view()),
    path("api/providers", ops.PublicProviders.as_view()),
    path("api/admin/summary", ops.Summary.as_view()),
    path("api/admin/payments", ops.PaymentList.as_view()),
    path("api/admin/payments/<uuid:pk>", ops.PaymentDetail.as_view()),
    path("api/admin/payments/<uuid:pk>/action", ops.PaymentAction.as_view()),
    path("api/admin/providers/<str:name>", ops.ProviderToggle.as_view()),
    path("api/admin/currency-rate", ops.CurrencyRateView.as_view()),
    path("api/admin/plans", ops.AdminPlanListCreate.as_view()),
    path("api/admin/plans/<uuid:pk>", ops.AdminPlanDetail.as_view()),
    path("api/admin/plans/<uuid:pk>/espees-product", ops.EspeesPlanProduct.as_view()),
    path("api/admin/audit", ops.AuditList.as_view()),
    path("api/me", MeView.as_view()),
    path("api/me/codes", MyCodesView.as_view()),
    path("api/me/transactions", TransactionList.as_view()),
    path("api/me/notifications", NotificationList.as_view()),
    path("api/me/notifications/read", MarkRead.as_view()),
]
