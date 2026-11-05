import hmac

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.plans.models import Plan

from .models import Payment
from .providers.base import ProviderError
from .services import check_payment, expire_stale, initiate_payment
from .tasks import poll_payment


class PaymentSerializer(serializers.ModelSerializer):
    access_code = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "provider", "amount", "currency", "status", "checkout_url", "created_at", "access_code"]

    def get_access_code(self, p):
        # The code is only ever shown once the payment is confirmed
        if p.status != Payment.SUCCESSFUL or not hasattr(p, "access_code"):
            return None
        from apps.access_codes.services import decrypt
        return decrypt(p.access_code)


class CreateOrderSerializer(serializers.Serializer):
    plan = serializers.SlugRelatedField(slug_field="code", queryset=Plan.objects.filter(is_active=True))
    provider = serializers.ChoiceField(choices=[Order.FLUTTERWAVE, Order.ESPEES])
    idempotency_key = serializers.CharField(max_length=64)


class CreateOrderView(APIView):
    throttle_scope = "payments"

    def post(self, request):
        s = CreateOrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            order, payment = initiate_payment(request.user, d["plan"], d["provider"], d["idempotency_key"])
        except ProviderError:
            return Response({"error": "provider_unavailable",
                             "message": "That payment method is unavailable right now. Try the other option."},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response({"order_id": str(order.id), "payment": PaymentSerializer(payment).data},
                        status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    """The frontend polls this after the customer returns from the provider."""

    def get(self, request, pk):
        payment = get_object_or_404(Payment.objects.select_related("access_code"), pk=pk, order__user=request.user)
        unresolved = payment.status in (Payment.INITIATED, Payment.PENDING)
        stale = not payment.last_checked_at or (timezone.now() - payment.last_checked_at).total_seconds() > 5
        if unresolved and stale and not payment.provider_reference.startswith("pending-"):
            try:
                check_payment(payment.id)
            except ProviderError:
                pass  # keep showing "checking"; the background job will retry
            payment = Payment.objects.select_related("access_code").get(pk=pk)
            expire_stale(payment)
            payment.refresh_from_db()
        return Response(PaymentSerializer(payment).data)


class FlutterwaveWebhook(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = settings.FLUTTERWAVE_WEBHOOK_HASH
        sent = request.headers.get("verif-hash", "")
        if not secret or not hmac.compare_digest(sent, secret):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        data = request.data.get("data") or {}
        ref = data.get("tx_ref")
        payment = Payment.objects.filter(provider="flutterwave", provider_reference=ref).first() if ref else None
        if payment:
            # Never trust the webhook body: re-check with Flutterwave in the background
            try:
                poll_payment.delay(str(payment.id))
            except Exception:  # queue down: check inline; the 15-minute job is the last safety net
                try:
                    check_payment(payment.id, "webhook")
                except ProviderError:
                    pass
        return Response({"received": True})
